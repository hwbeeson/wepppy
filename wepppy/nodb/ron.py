# Copyright (c) 2016-2018, University of Idaho
# All rights reserved.
#
# Roger Lew (rogerlew@gmail.com)
#
# The project described was supported by NSF award number IIA-1301792
# from the NSF Idaho EPSCoR Program and by the National Science Foundation.

# standard libraries
import os

from os.path import exists as _exists
from os.path import join as _join
from os.path import split as _split
from os.path import isdir

import shutil

# non-standard
import jsonpickle
import utm
import what3words

# wepppy
from wepppy.all_your_base.geo.webclients import wmesque_retrieve
from wepppy.all_your_base.geo import haversine, read_raster, utm_srid

# wepppy submodules
from .base import (
    NoDbBase,
    TriggerEvents
)


_thisdir = os.path.dirname(__file__)


class Map(object):
    def __init__(self, extent, center, zoom, cellsize=30.0):
        assert len(extent) == 4

        _extent = [float(v) for v in extent]
        l, b, r, t = _extent
        assert l < r
        assert b < t

        self.extent = [float(v) for v in _extent]  # in decimal degrees
        self.center = [float(v) for v in center]
        self.zoom = int(zoom)
        self.cellsize = cellsize

        # e.g. (395201.3103811303, 5673135.241182375, 32, 'U')
        ul_x, ul_y, zone_number, zone_letter = utm.from_latlon(latitude=t, longitude=l)
        ul_x = float(ul_x)
        ul_y = float(ul_y)
        self.utm = ul_x, ul_y, zone_number, zone_letter

        lr_x, lr_y, _, _ = utm.from_latlon(longitude=r, latitude=b, force_zone_number=zone_number)
        self._ul_x = float(ul_x)  # in utm
        self._ul_y = float(ul_y)
        self._lr_x = float(lr_x)
        self._lr_y = float(lr_y)

        self._num_cols = int(round((lr_x - ul_x) / cellsize))
        self._num_rows = int(round((ul_y - lr_y) / cellsize))

    @property
    def utm_zone(self):
        return self.utm[2]

    @property
    def zone_letter(self):
        return self.utm[3]

    @property
    def srid(self):
        return utm_srid(self.utm_zone, self.northern)

    @property
    def northern(self):
        return self.extent[3] > 0.0

    @property
    def ul_x(self):
        if hasattr(self, '_ul_x'):
            return self._ul_x

        l, b, r, t = self.extent
        ul_x, ul_y, zone_number, zone_letter = utm.from_latlon(latitude=t, longitude=l)
        self._ul_x = float(ul_x)
        self._ul_y = float(ul_y)

        return ul_x

    @property
    def ul_y(self):
        if hasattr(self, '_ul_y'):
            return self._ul_y

        l, b, r, t = self.extent
        ul_x, ul_y, zone_number, zone_letter = utm.from_latlon(latitude=t, longitude=l)
        self._ul_x = float(ul_x)
        self._ul_y = float(ul_y)

        return ul_y

    @property
    def lr_x(self):
        if hasattr(self, '_lr_x'):
            return self._lr_x

        l, b, r, t = self.extent
        lr_x, lr_y, zone_number, zone_letter = utm.from_latlon(latitude=b, longitude=r)
        self._lr_x = float(lr_x)
        self._lr_y = float(lr_y)

        return lr_x

    @property
    def lr_y(self):
        if hasattr(self, '_lr_y'):
            return self._lr_y

        l, b, r, t = self.extent
        lr_x, lr_y, zone_number, zone_letter = utm.from_latlon(latitude=b, longitude=r)
        self._lr_x = float(lr_x)
        self._lr_y = float(lr_y)

        return lr_y

    @property
    def utm_extent(self):
        return self.ul_x, self.lr_y, self.lr_x, self.ul_y

    @property
    def num_cols(self):
        if hasattr(self, '_num_cols'):
            return self._num_cols

        self._num_cols = int(round((self.lr_x - self.ul_x) / self.cellsize))
        return self._num_cols

    @property
    def num_rows(self):
        if hasattr(self, '_num_rows'):
            return self._num_rows

        self._num_rows = int(round((self.lr_x - self.ul_x) / self.cellsize))
        return self._num_rows

    @property
    def shape(self):
        l, b, r, t = self.extent
        px_w = int(haversine((l, b), (l, t)) * 1000 / self.cellsize)
        px_h = int(haversine((l, b), (r, b)) * 1000 / self.cellsize)
        return px_w, px_h

    @property
    def bounds_str(self):
        """
        returns extent formatted leaflet
        """
        l, b, r, t = self.extent
        sw = [b, l]
        ne = [t, r]
        return str([sw, ne])

    def utm_to_px(self, easting, northing):
        """
        return the utm coords from pixel coords
        """

        # unpack variables for instance
        cellsize, num_cols, num_rows = self.cellsize, self.num_cols, self.num_rows
        ul_x, ul_y, lr_x, lr_y = self.ul_x, self.ul_y, self.lr_x, self.lr_y

        x = int(round((easting - ul_x) / cellsize))
        y = int(round((northing - ul_y) / -cellsize))

        assert 0 <= y < num_rows, (y, (num_rows, num_cols))
        assert 0 <= x < num_cols, (x, (num_rows, num_cols))

        return x, y

    def lnglat_to_px(self, long, lat):
        """
        return the x,y pixel coords of long, lat
        """

        # unpack variables for instance
        cellsize, num_cols, num_rows = self.cellsize, self.num_cols, self.num_rows
        ul_x, ul_y, lr_x, lr_y = self.ul_x, self.ul_y, self.lr_x, self.lr_y

        # find easting and northing
        x, y, _, _ = utm.from_latlon(lat, long, self.utm_zone)

        # assert this makes sense with the stored extent
        assert round(x) >= round(ul_x), (x, ul_x)
        assert round(x) <= round(lr_x), (x, lr_x)
        assert round(y) >= round(lr_y), (y, lr_y)
        assert round(y) <= round(y), (y, ul_y)

        # determine pixel coords
        _x = int(round((x - ul_x) / cellsize))
        _y = int(round((ul_y - y) / cellsize))

        # sanity check on the coords
        assert 0 <= _x < num_cols, str(x)
        assert 0 <= _y < num_rows, str(y)

        return _x, _y

    def px_to_utm(self, x, y):
        """
        return the utm coords from pixel coords
        """

        # unpack variables for instance
        cellsize, num_cols, num_rows = self.cellsize, self.num_cols, self.num_rows
        ul_x, ul_y, lr_x, lr_y = self.ul_x, self.ul_y, self.lr_x, self.lr_y

        assert 0 <= x < num_cols
        assert 0 <= y < num_rows

        easting = ul_x + cellsize * x
        northing = ul_y - cellsize * y

        return easting, northing

    def lnglat_to_utm(self, lng, lat):
        """
        return the utm coords from lnglat coords
        """
        x, y, _, _ = utm.from_latlon(latitude=lat, longitude=lng, force_zone_number=self.utm_zone)
        return float(x), float(y)

    def px_to_lnglat(self, x, y):
        """
        return the long/lat (WGS84) coords from pixel coords
        """

        easting, northing = self.px_to_utm(x, y)
        lat, lng, _, _ = utm.to_latlon(easting=easting, northing=northing,
                                       zone_number=self.utm_zone, northern=self.northern)
        return float(lng), float(lat)

    def raster_intersection(self, extent, raster_fn, discard=None):
        """
        returns the subset of pixel values of raster_fn that are within the extent
        :param extent: l, b, r, t in decimal degrees
        :param raster_fn: path to a thematic raster with the same extent, projection, and cellsize as this instance
        :param None or iterable, throwaway these values before returning

        :return:  sorted list of the values
        """
        if not _exists(raster_fn):
            return []

        assert extent[0] < extent[2]
        assert extent[1] < extent[3]

        map = self.map

        x0, y0 = map.lnglat_to_pixel(extent[0], extent[3])
        xend, yend = map.lnglat_to_pixel(extent[2], extent[1])

        assert x0 < xend
        assert y0 < yend

        data, transform, proj = read_raster(raster_fn)
        the_set = set(data[x0:xend, y0:yend].flatten())
        if discard is not None:
            for val in discard:
                the_set.discard(val)
        return sorted(the_set)


class RonNoDbLockedException(Exception):
    pass


class Ron(NoDbBase):
    """
    Manager that keeps track of project details
    and coordinates access of NoDb instances.
    """
    __name__ = 'Ron'

    def __init__(self, wd, cfg_fn='0.cfg'):
        super(Ron, self).__init__(wd, cfg_fn)

        self.lock()

        # noinspection PyBroadException
        try:
            self._configname = self.config_get_str('general', 'name')

            # Map
            self._cellsize = self.config_get_float('general', 'cellsize')
            self._center0 = self.config_get_raw('map', 'center0')
            self._zoom0 = self.config_get_int('map', 'zoom0')

            _boundary = self.config_get_path('map', 'boundary')
            self._boundary = _boundary

            # DEM
            dem_dir = self.dem_dir
            if not _exists(dem_dir):
                os.mkdir(dem_dir)

            self._dem_db = self.config_get_str('general', 'dem_db')

            _dem_map = self.config_get_path('general', 'dem_map')
            self._dem_map = _dem_map

            if self.dem_map is not None:
                shutil.copyfile(self.dem_map, self.dem_fn)

            # Landuse
            self._enable_landuse_change = self.config_get_bool('landuse', 'enable_landuse_change')

            # Project
            self._name = ''
            self._map = None
            self._w3w = None

            self._locales = self.config_get_list('general', 'locales')

            export_dir = self.export_dir
            if not _exists(export_dir):
                os.mkdir(export_dir)

            # initialize the other controllers here
            # this will create the other .nodb files
            import wepppy

            # gotcha: need to import the nodb submodules
            # through wepppy to avoid circular references
            watershed = wepppy.nodb.Watershed(wd, cfg_fn)
            if watershed.delineation_backend == wepppy.nodb.DelineationBackend.TOPAZ:
                wepppy.nodb.Topaz(wd, cfg_fn)

            wepppy.nodb.Landuse(wd, cfg_fn)
            wepppy.nodb.Soils(wd, cfg_fn)
            wepppy.nodb.Climate(wd, cfg_fn)
            wepppy.nodb.Wepp(wd, cfg_fn)
            wepppy.nodb.Unitizer(wd, cfg_fn)
            wepppy.nodb.WeppPost(wd, cfg_fn)
            wepppy.nodb.Observed(wd, cfg_fn)

            if 'lt' in self.mods:
                wepppy.nodb.mods.locations.LakeTahoe(wd, cfg_fn)

            if 'portland' in self.mods:
                wepppy.nodb.mods.locations.PortlandMod(wd, cfg_fn)

            if 'seattle' in self.mods:
                wepppy.nodb.mods.locations.SeattleMod(wd, cfg_fn)

            if 'general' in self.mods:
                wepppy.nodb.mods.locations.GeneralMod(wd, cfg_fn)

            if 'turkey' in self.mods:
                wepppy.nodb.mods.locations.TurkeyMod(wd, cfg_fn)

            if 'baer' in self.mods or 'disturbed' in self.mods:
                assert not ('baer' in self.mods and 'disturbed' in self.mods)

                if 'baer' in self.mods:
                    Mod = wepppy.nodb.mods.Baer
                else:
                    Mod = wepppy.nodb.mods.Disturbed

                baer = Mod(wd, cfg_fn)
                sbs_map = self.config_get_path('landuse', 'sbs_map')

                if sbs_map is not None:
                    from wepppy.nodb.mods import MODS_DIR
                    sbs_map = sbs_map.replace('MODS_DIR', MODS_DIR)

                    # sbs_map = _join(_thisdir, sbs_map)
                    assert _exists(sbs_map), (sbs_map, os.path.abspath(sbs_map))
                    assert not isdir(sbs_map)

                    sbs_path = _join(baer.baer_dir, 'sbs.tif')
                    shutil.copyfile(sbs_map, sbs_path)

                    baer.validate(_split(sbs_path)[-1])

            if 'rred' in self.mods:
                wepppy.nodb.mods.Rred(wd, cfg_fn)

            if 'debris_flow' in self.mods:
                wepppy.nodb.mods.DebrisFlow(wd, cfg_fn)

            if 'ash' in self.mods:
                wepppy.nodb.mods.Ash(wd, cfg_fn)
                wepppy.nodb.mods.AshPost(wd, cfg_fn)

            if 'rap' in self.mods:
                wepppy.nodb.mods.RAP(wd, cfg_fn)

            if 'shrubland' in self.mods:
                wepppy.nodb.mods.Shrubland(wd, cfg_fn)

            if 'rangeland_cover' in self.mods:
                wepppy.nodb.mods.RangelandCover(wd, cfg_fn)

            if 'rhem' in self.mods:
                wepppy.nodb.mods.Rhem(wd, cfg_fn)
                wepppy.nodb.mods.RhemPost(wd, cfg_fn)

            if 'treecanopy' in self.mods:
                wepppy.nodb.mods.Treecanopy(wd, cfg_fn)

            self.dump_and_unlock()

            self.trigger(TriggerEvents.ON_INIT_FINISH)

        except Exception:
            self.unlock('-f')
            raise
    #
    # Required for NoDbBase Subclass
    #

    # noinspection PyPep8Naming
    @staticmethod
    def getInstance(wd):
        with open(_join(wd, 'ron.nodb')) as fp:
            db = jsonpickle.decode(fp.read())
            assert isinstance(db, Ron), db

            if _exists(_join(wd, 'READONLY')):
                db.wd = os.path.abspath(wd)
                return db

            if os.path.abspath(wd) != os.path.abspath(db.wd):
                db.wd = wd
                db.lock()
                db.dump_and_unlock()

            return db

    @property
    def _nodb(self):
        return _join(self.wd, 'ron.nodb')

    @property
    def _lock(self):
        return _join(self.wd, 'ron.nodb.lock')

    @property
    def configname(self) -> str:
        return self._configname

    @property
    def enable_landuse_change(self) -> bool:
        return self._enable_landuse_change

    #
    # map
    #
    @property
    def center0(self):
        if self.map is None:
            return self._center0
        else:
            return self.map.center[::-1]

    @property
    def zoom0(self):
        if self.map is None:
            return self._zoom0
        else:
            return self.map.zoom

    @property
    def cellsize(self):
        return self._cellsize

    @property
    def boundary(self):
        return self._boundary

    @property
    def map(self):
        return self._map

    def set_map(self, extent, center, zoom):
        self.lock()

        # noinspection PyBroadException
        try:
            self._map = Map(extent, center, zoom, self.cellsize)
            w3w_api_key = self.config_get_str('general', 'w3w_api_key')

            lng, lat = self.map.center
            w3w_geocoder = what3words.Geocoder(w3w_api_key)
            try:
                self._w3w = w3w_geocoder.reverse(lat=lat, lng=lng)
            except:
                coord = what3words.Coordinates(lat=lat, lng=lng)
                self._w3w = w3w_geocoder.convert_to_3wa(coord)

            self.dump_and_unlock()

        except Exception:
            self.unlock('-f')
            raise

    @property
    def w3w(self):
        if hasattr(self, '_w3w'):
            if self._w3w is not None:
                return self._w3w.get('words', '')

        return ''

    @property
    def extent(self):
        if self.map is None:
            return None

        return self.map.extent

    #
    # name
    #
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self.lock()

        # noinspection PyBroadException
        try:
            self._name = value
            self.dump_and_unlock()

        except Exception:
            self.unlock('-f')
            raise

    @property
    def locales(self):
        if hasattr(self, '_locales'):
            return self._locales

        config_stem = self.config_stem

        if config_stem in ('au', 'au-fire'):
            return 'au',
        elif config_stem in ('eu', 'eu-75', 'eu-fire', 'eu-fire2'):
            return 'eu',
        elif config_stem in ('lt', 'lt-fire-future-snow', 'lt-wepp_347f3bd', 'lt-wepp_bd16b69-snow'):
            return 'us', 'lt',
        elif config_stem in ('portland', 'portland-simfire-eagle-snow', 'portland-simfire-norse-snow',
                             'portland-snow', 'portland-wepp_64bf5aa_snow', 'portland-wepp_347f3bd',
                             'portland-wepp_bd16b69'):
            return 'us', 'portland'
        elif config_stem in ('seattle-simfire-eagle-snow', 'seattle-simfire-norse-snow', 'seattle-snow'):
            return 'us', 'seattle'
        else:
            return 'us',

    @property
    def has_ash_results(self):
        if 'ash' not in self.mods:
            return False

        from wepppy.nodb.mods import Ash
        ash = Ash.getInstance(self.wd)
        return ash.has_ash_results

    @property
    def has_sbs(self):
        if 'baer' in self.mods:
            from wepppy.nodb.mods import Baer
            baer = Baer.getInstance(self.wd)
            return baer.has_map
        elif 'disturbed' in self.mods:
            from wepppy.nodb.mods import Disturbed
            baer = Disturbed.getInstance(self.wd)
            return baer.has_map

        return False

    @property
    def dem_db(self):
        return getattr(self, '_dem_db', self.config_get_str('general', 'dem_db'))

    @dem_db.setter
    def dem_db(self, value):

        self.lock()

        # noinspection PyBroadException
        try:
            self._dem_db = value
            self.dump_and_unlock()

        except Exception:
            self.unlock('-f')
            raise

    @property
    def dem_map(self):
        if not hasattr(self, '_dem_map'):
            return None

        return self._dem_map

    @dem_map.setter
    def dem_map(self, value):

        self.lock()

        # noinspection PyBroadException
        try:
            self._dem_map = value
            self.dump_and_unlock()

        except Exception:
            self.unlock('-f')
            raise

    #
    # dem
    #
    def fetch_dem(self):
        assert self.map is not None
        wmesque_retrieve(self.dem_db, self.map.extent,
                         self.dem_fn, self.map.cellsize)

        assert _exists(self.dem_fn)

    @property
    def has_dem(self):
        return _exists(self.dem_fn)

    #
    # summary
    #
    def subs_summary(self):
        wd = self.wd
        import wepppy.nodb
        watershed = wepppy.nodb.Watershed.getInstance(wd)
        translator = watershed.translator_factory()
        soils = wepppy.nodb.Soils.getInstance(wd)
        climate = wepppy.nodb.Climate.getInstance(wd)
        landuse = wepppy.nodb.Landuse.getInstance(wd)

        summaries = []
        for wepp_id in translator.iter_wepp_sub_ids():
            topaz_id = translator.top(wepp=wepp_id)

            summaries.append(
                dict(meta=dict(hill_type='Hillslope',
                               topaz_id=topaz_id,
                               wepp_id=wepp_id),
                     watershed=watershed.sub_summary(topaz_id),
                     soil=soils.sub_summary(topaz_id),
                     climate=climate.sub_summary(topaz_id),
                     landuse=landuse.sub_summary(topaz_id)))

        return summaries

    def sub_summary(self, topaz_id=None, wepp_id=None):
        wd = self.wd
        import wepppy.nodb
        watershed = wepppy.nodb.Watershed.getInstance(wd)
        translator = watershed.translator_factory()
        soils = wepppy.nodb.Soils.getInstance(wd)
        climate = wepppy.nodb.Climate.getInstance(wd)
        landuse = wepppy.nodb.Landuse.getInstance(wd)

        if topaz_id is None:
            topaz_id = translator.top(wepp=wepp_id)

        if wepp_id is None:
            wepp_id = translator.wepp(top=topaz_id)

        return dict(
            meta=dict(hill_type='Hillslope', topaz_id=topaz_id,
                      wepp_id=wepp_id),
            watershed=watershed.sub_summary(topaz_id),
            soil=soils.sub_summary(topaz_id),
            climate=climate.sub_summary(topaz_id),
            landuse=landuse.sub_summary(topaz_id)
        )

    def chns_summary(self):
        wd = self.wd
        import wepppy.nodb
        watershed = wepppy.nodb.Watershed.getInstance(wd)
        translator = watershed.translator_factory()
        soils = wepppy.nodb.Soils.getInstance(wd)
        climate = wepppy.nodb.Climate.getInstance(wd)
        landuse = wepppy.nodb.Landuse.getInstance(wd)

        summaries = []
        for wepp_id in translator.iter_wepp_chn_ids():
            topaz_id = translator.top(wepp=wepp_id)
            chn_enum = translator.chn_enum(top=topaz_id)

            summaries.append(
                dict(meta=dict(hill_type='Channel',
                               topaz_id=topaz_id,
                               wepp_id=wepp_id,
                               chn_enum=chn_enum),
                     watershed=watershed.chn_summary(topaz_id),
                     soil=soils.chn_summary(topaz_id),
                     climate=climate.chn_summary(topaz_id),
                     landuse=landuse.chn_summary(topaz_id)))

        return summaries

    def chn_summary(self, topaz_id=None, wepp_id=None):
        wd = self.wd
        import wepppy.nodb
        watershed = wepppy.nodb.Watershed.getInstance(wd)
        translator = watershed.translator_factory()
        soils = wepppy.nodb.Soils.getInstance(wd)
        climate = wepppy.nodb.Climate.getInstance(wd)
        landuse = wepppy.nodb.Landuse.getInstance(wd)

        if topaz_id is None:
            topaz_id = translator.top(wepp=wepp_id)

        if wepp_id is None:
            wepp_id = translator.wepp(top=topaz_id)

        chn_enum = translator.chn_enum(top=topaz_id)

        return dict(
            meta=dict(hill_type='Channel', topaz_id=topaz_id,
                      wepp_id=wepp_id, chn_enum=chn_enum),
            watershed=watershed.chn_summary(topaz_id),
            soil=soils.chn_summary(topaz_id),
            climate=climate.chn_summary(topaz_id),
            landuse=landuse.chn_summary(topaz_id)
        )
