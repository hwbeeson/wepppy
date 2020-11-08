import json
from math import atan2, pi, hypot
from typing import Union, List

import numpy as np

from wepppy.all_your_base import isfloat


def is_channel(topaz_id: Union[int, str]) -> bool:
    return str(topaz_id).endswith('4')


def garbrecht_length(distances: List[List[float]]) -> float:
    """
    calculates the length of a subcatchment from the flowpaths
    contained within the subcatchment. The length is weighted_flowpaths
    by the flowpaths length relative to its area.

    distances should be an array of distances between cells along the
    flowpath (not cumulative distance)

    eq. 3.4 in Thomas Cochrane's Dissertation
    # """
    x = np.array([np.sum(d) for d in distances])
    a = np.array([len(d) for d in distances], dtype=np.float64)
    return float(np.sum(x * a) / np.sum(a))


def cummnorm_distance(distance: List[float]) -> np.array:
    """
    builds and returns cumulative normalized distance array from an array
    of cell-to-cell distances
    """
    assert len(distance) > 0

    if len(distance) == 1:
        assert distance[0] > 0.0
        return np.array([0, 1])

    distance_p = np.cumsum(np.array(distance, np.float64))
    distance_p -= distance_p[0]
    distance_p /= distance_p[-1]
    return distance_p


def representative_normalized_elevations(x: List[float], dy: List[float]) -> List[float]:
    """
    x should be a normed distance array between 0 and 1
    dy is an array of slopes

    returns normalized elevations (relative to the length of x)
    """
    assert len(x) == len(dy), (x, dy)
    assert x[0] == 0.0
    assert x[-1] == 1.0

    # calculate the positions, assume top of hillslope is 0 y
    y = [0.0]
    for i in range(len(dy) - 1):
        step = x[i+1] - x[i]
        y.append(y[-1] - step * dy[i])

    return y


def read_geojson(fname):
    data = json.loads(open(fname).read())

    d = {}
    for feature in data['features']:
        top = feature['properties']['TopazID']
        d[top] = np.array(feature['geometry']['coordinates'][0])

    return d


def interpolate_slp(distances, slopes, max_points):
    _s = np.array(slopes)
    _d = np.array(distances)

    if _s.shape == (1,) and _d.shape == (2,):  # slope is a single cell
        _s = np.array([slopes[0], slopes[0]])

    assert _s.shape == _d.shape, str([_s.shape, _d.shape])

    for i in range(len(_d)-1):
        assert _d[i] < _d[i+1], distances

    assert _d[0] == 0.0
    assert _d[-1] == 1.0

    npts = len(_d)

    # interpolate if there are too many slope points
    if npts > max_points:
        _d2 = np.linspace(0.0, 1.0, max_points)
        _s2 = np.interp(_d2, _d, _s)
        _d, _s = _d2, _s2

    return _d, _s


def write_slp(aspect, width, cellsize, length, slope, distance_p, fp, version=97.3, max_points=19):
    """
    writes a slope file in the 97.3 format for WEPP
    """
    assert isfloat(aspect)
    assert isfloat(width)
    assert isfloat(length)
    assert isfloat(cellsize)

    _d, _s = distance_p, slope

    nofes = 1
    npts = len(_d)
    if npts > max_points:
        _d, _s = interpolate_slp(distance_p, slope, max_points)
        npts = len(_d)

    if version == 97.3:
        _slp = '97.3\n{nofes}\n{aspect} {width}\n{npts} {length}\n{defs} '
        defs = ' '.join(['%0.4f, %0.5f' % ds for ds in zip(_d, _s)])

        fp.write(_slp.format(nofes=nofes, aspect=aspect, width=width,
                             npts=npts, length=length, defs=defs))

    else:
        _slp = '{aspect} {cellsize}\n{npts} {length}\n{defs} \n'
        defs = ' '.join(['%0.4f %0.5f' % ds for ds in zip(_d, _s)])

        fp.write(_slp.format(nofes=nofes, aspect=aspect, cellsize=float(cellsize),
                             npts=npts, length=length, defs=defs))


def identify_subflows(flowpaths: List[np.array]) -> List[List[int]]:
    """
    given an ndarray of flowpaths flowpath (n, 2) for a subcatchment
    identify which flowpaths travel over the same path down the
    hillslope. These are grouped into subflows of flowpath indices
    """
    # if there is only 1 flowpath then there are no subflows
    if len(flowpaths) == 1:
        return [[0]]

    # create a dictionary of px coord tuples so we can point back to the
    # index of the flowpaths list. This is aligned
    # with slopes and distance.
    fps_d = {}
    for k, fp in enumerate(flowpaths):
        fps_d[k] = list(set((fp[j, 0], fp[j, 1]) for j in range(fp.shape[0])))

    # here we create a list of tuples containing
    # the flow indices and the length of the flows
    # we want to iterate through the flows in
    # descending flow length
    lns = [(k, len(v)) for k, v in fps_d.items()]

    # build an empty list to populate subflows
    subflows = []

    # iterate over the flowpaths. If a subflow is identified as
    # a subflow then add it to the subflows index list
    # otherwise create a new subflow list
    for i, n in sorted(lns, key=lambda y: y[1], reverse=True):
        # unpack the set of pixel coords for the subflow
        fp0 = fps_d[i]

        # this gets set to 1 if fp0 is identified as a subflow
        issub = 0

        for j, fp1_indx_arr in enumerate(subflows):
            # because we are iterating in descending order the
            # first index of each subflow index list will
            # be the longest
            fp1 = fps_d[fp1_indx_arr[0]]

            # is fp0 a subset of fp1
            if fp0 <= fp1:
                subflows[j].append(i)
                issub = 1
                break

        # fp0 is not a subset so create a new subflow list
        if not issub:
            subflows.append([i])

    return subflows


def weighted_slope_average(areas, slopes, lengths, max_points=19):
    """
    calculates weighted slopes based on the flowpaths contained on the hillslope

    eq. 3.3 in Thomas Cochrane's Dissertation
    """
    areas = np.ceil(areas)

    # determine longest flowpath
    i = int(np.argmax(lengths))
    longest = float(lengths[i])

    # determine number of points to define slope
    num_points = len(lengths)
    if num_points > max_points:
        num_points = max_points

    if num_points == 1:
        slope = float(slopes[i])
        return [slope, slope], [0.0, 1.0]

    # determine weights for each flowpath
    kps = np.array([L * a for L, a in zip(lengths, areas)])

    # build an array with equally spaced points to interpolate on
    distance_p = np.linspace(0, longest, num_points)

    # this will hold the weighted slope estimates
    eps = []

    # we will weight the slope at each distance away from the channel
    for d_p in distance_p:
        num = 0  # to hold numerator value
        kpsum = 0  # to hold k_p sum

        for slp, rcd, kp in zip(slopes, areas, kps):

            # we only want to interpolate where the slope is defined
            if d_p - 1e-6 > rcd:
                continue

            num += slp * kp
            kpsum += kp

        # store the weighted slope estimate
        eps.append(num / kpsum)

    # normalize distance_p array
    distance_p /= longest

    # reverse weighted slopes and return
    w_slopes = np.array(eps[::-1])

    return w_slopes.flatten().tolist(), distance_p.tolist()


def compute_direction(head: List, tail: List) -> float:
    a = atan2(tail[1] - head[1],
              head[0] - tail[0]) * (180.0 / pi) - 180.0

    if a < 0:
        return a + 360.0

    return a


slope_template = """\
{aspect} {profile_width}
{num_points} {length}
{profile}"""
colordict = {
  0:     "#787878",
  "n":  ["#9afb0c", "#9ddd5e", "#9fc085"],
  "ne": ["#00ad43", "#3dab71", "#72a890"],
  "e":  ["#0068c0", "#5078b6", "#7c8ead"],
  "se": ["#6c00a3", "#77479d", "#8c75a0"],
  "s":  ["#ca009c", "#c04d9c", "#b47ba1"],
  "sw": ["#ff5568", "#e76f7a", "#cb8b8f"],
  "w":  ["#ffab47", "#e2a66c", "#c5a58a"],
  "nw": ["#f4fa00", "#d6db5e", "#bdbf89"]
}
c_slope_breaks = [0.05, 0.15, 0.30]


def slp_asp_color(slope: float, aspect: float) -> str:
    aspect %= 360.0

    i = 0
    for j, brk in enumerate(c_slope_breaks):
        if slope > brk:
            i = j + 1

    if i == 0:
        return colordict[0]

    cat_asp = "n"
    if 22.5 < aspect < 67.5:
        cat_asp = "ne"
    elif aspect < 112.5:
        cat_asp = "e"
    elif aspect < 157.5:
        cat_asp = "se"
    elif aspect < 202.5:
        cat_asp = "s"
    elif aspect < 247.5:
        cat_asp = "sw"
    elif aspect < 292.5:
        cat_asp = "w"
    elif aspect < 337.5:
        cat_asp = "nw"

    return colordict[cat_asp][i-1]


def rect_to_polar(d):
    point = d['point']
    origin = d['origin']
    refvec = d['refvec']

    # Vector between point and the origin: v = p - o
    vector = [point[0] - origin[0], point[1] - origin[1]]

    # Length of vector: ||v||
    lenvector = hypot(vector[0], vector[1])

    # If length is zero there is no angle
    if lenvector == 0:
        return -pi

    normalized = [vector[0]/lenvector, vector[1]/lenvector]
    dotprod = normalized[0] * refvec[0] + normalized[1] * refvec[1]
    diffprod = refvec[1] * normalized[0] - refvec[0] * normalized[1]
    angle = atan2(diffprod, dotprod)

    angle %= 2 * pi

    return angle


class CentroidSummary(object):
    def __init__(self, **kwds):
        self.px = tuple(int(v) for v in kwds['px'])
        self.lnglat = tuple(float(v) for v in kwds['lnglat'])


class SummaryBase(object):
    def __init__(self, **kwds):
        topaz_id = kwds['topaz_id']
        if topaz_id is not None:
            topaz_id = int(topaz_id)
        self.topaz_id = topaz_id

        wepp_id = kwds['wepp_id']
        if wepp_id is not None:
            wepp_id = int(wepp_id)
        self.wepp_id = wepp_id

        self.length = float(kwds['length'])
        self.width = float(kwds['width'])
        self.area = float(kwds['area'])
        self.aspect = float(kwds['aspect'])
        self.direction = float(kwds['direction'])
        self.slope_scalar = float(kwds['slope_scalar'])
        self.color = str(kwds['color'])
        self.centroid = kwds['centroid']
        self.distance_p = tuple(kwds['distance_p'])

        self._max_points = 19

        self.w_slopes = None
        self.slopes = None

    @property
    def num_points(self) -> int:
        npts = len(self.distance_p)
        max_points = self.max_points
        return (npts, max_points)[npts > max_points]

    @property
    def max_points(self) -> int:
        return self._max_points

    @property
    def profile(self) -> str:
        max_points = self.max_points
        distance_p = self.distance_p

        try:
            slopes = self.w_slopes
            if slopes is None:
                slopes = self.slopes
        except AttributeError:
            slopes = self.slopes

        _d, _s = distance_p, slopes

        npts = len(_d)
        if npts > max_points:
            _d, _s = interpolate_slp(_d, _s, max_points)

        return ' '.join(["%0.6f, %0.3f" % (d, s) for d, s in zip(_d, _s)])

    # noinspection PyUnresolvedReferences
    def as_dict(self):
        d = dict(
            fname=self.fname,
            topaz_id=self.topaz_id,
            wepp_id=self.wepp_id,
            length=self.length,
            width=self.width,
            area=self.area,
            aspect=self.aspect,
            direction=self.direction,
            slope_scalar=self.slope_scalar,
            color=self.color,
            centroid=self.centroid.lnglat
        )

        try:
            d['order'] = self.order
        except:
            pass

        try:
            d['channel_type'] = self.channel_type
        except:
            pass

        if hasattr(self, 'chn_wepp_width'):
            d['chn_wepp_width'] = self.chn_wepp_width

        if hasattr(self, 'cell_width'):
            d['chn_wepp_width'] = self.chn_wepp_width

        try:
            d['slopes'] = self.slopes
            d['coords'] = self.coords
        except:
            pass

        if hasattr(self, 'fp_longest'):
            d['fp_longest'] = self.fp_longest
        if hasattr(self, 'fp_longest_length'):
            d['fp_longest_length'] = self.fp_longest_length
        if hasattr(self, 'fp_longest_slope'):
            d['fp_longest_slope'] = self.fp_longest_slope

        return d


class HillSummary(SummaryBase):
    def __init__(self, **kwds):
        super(HillSummary, self).__init__(**kwds)
        self.w_slopes = tuple(kwds['w_slopes'])
        self.pourpoint = tuple(kwds['pourpoint'])
        self.fp_longest = kwds.get('fp_longest', None)
        self.fp_longest_length = kwds.get('fp_longest_length', None)
        self.fp_longest_slope = kwds.get('fp_longest_slope', None)

    @property
    def fname(self) -> str:
        return 'hill_%i.slp' % self.topaz_id

    @property
    def pourpoint_coord(self):
        return str(tuple([int(v) for v in self.pourpoint])).replace(' ', '')


class ChannelSummary(SummaryBase):
    def __init__(self, **kwds):
        super(ChannelSummary, self).__init__(**kwds)
        self.slopes = tuple(kwds['slopes'])
        self._order = kwds.get('order', None)
        self.isoutlet = kwds['isoutlet']
        self.head = kwds['head']
        self.tail = kwds['tail']
        self.chn_enum = int(kwds['chn_enum'])
        self._chn_type = kwds['chn_type']

    @property
    def head_coord(self):
        return str(tuple([int(v) for v in self.head])).replace(' ', '')

    @property
    def tail_coord(self):
        return str(tuple([int(v) for v in self.tail])).replace(' ', '')

    @property
    def fname(self) -> str:
        return 'chn_%i.slp' % self.topaz_id

    @property
    def order(self) -> int:
        return self._order

    @order.setter
    def order(self, value):
        self._order = int(value)

    @property
    def channel_type(self) -> str:
        return getattr(self, '_chn_type', 'Default')

        # return 'Default'
        # return ('OnEarth 1', 'OnGravel 1', 'OnRock 2')[int([None, 0, 0, 1, 1, 1, 2, 2][self.order])]

    @channel_type.setter
    def channel_type(self, value):
        self._chn_type = value

    @property
    def chn_wepp_width(self) -> int:
        """returns channel width in meters (not pixel units)"""
        return [None, 1, 2, 2, 3, 3, 3, 4, 4][self.order]


class FlowpathSummary(SummaryBase):
    def __init__(self, **kwds):
        super(FlowpathSummary, self).__init__(**kwds)
        self.slopes = tuple(kwds['slopes'])
        self.coords = kwds['coords']

    @property
    def fname(self) -> str:
        return 'flow_%i.slp' % self.topaz_id