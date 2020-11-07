import os
from os.path import exists as _exists
from os.path import join as _join
from os.path import split as _split
import shutil

from collections import Counter

import numpy as np
import matplotlib.pyplot as plt

from wepppy.all_your_base.geo import (
    shapefile,
    wgs84_proj4,
    read_raster,
    build_mask,
    px_to_lnglat,
    centroid_px,
    GeoTransformer
)

from wepppy.all_your_base.geo.webclients import wmesque_retrieve


if __name__ == "__main__":
    cellsize = 90  # cellsize used to determine dominate mukey

    # clean the build directory
    if _exists('build'):
        shutil.rmtree('build')

    os.mkdir('build')

    # load the shapefile containing U.S. counties
    shp = "data/cb_2017_us_county_500k/cb_2017_us_county_500k"
    sf = shapefile.Reader(shp)
    header = [field[0] for field in sf.fields][1:]

    # loop through counties to determine dominate landuse
    fp = open('dom_mukeys_by_county.csv', 'w')  # successful results get stored here
    fpe = open('failed_counties.txt', 'w')  # problems get stored here by AFFGEOID
    for i, shape in enumerate(sf.iterShapes()):
        try:
            # unpack record
            record = {k: v for k, v in zip(header, sf.record(i))}
            print(record)
            fips = record['AFFGEOID']

            # determine bounds for surgo map
            print('fetch surgo map')
            bbox = shape.bbox
            pad = max(abs(bbox[0] - bbox[2]), abs(bbox[1] - bbox[3])) * 0.05
            map_center = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
            l, b, r, t = bbox
            bbox = [l - pad, b - pad, r + pad, t + pad]
            print(bbox)

            # fetch map
            ssurgo_fn = _join('build', '%s.tif' % fips)

            wmesque_retrieve('ssurgo/201703', bbox,
                             ssurgo_fn, cellsize)

            # read in map
            mukey_map, transform, utmproj4 = read_raster(ssurgo_fn)

            # transform coordinates in shape file to utm
            wgs2utm_transformer = GeoTransformer(src_proj4=wgs84_proj4, dst_proj4=utmproj4)
            points = [wgs2utm_transformer.transform(lng, lat) for lng, lat in shape.points]

            assert len(points) > 0

            # build a mask for the polygon of the county
            mask = build_mask(points, ssurgo_fn)

    #        plt.figure()
    #        plt.imshow(mask)
    #        plt.savefig(_join('build', 'ma_%s.png' % fips))

            # extract the mukeys inside the polygon
            indx, indy = np.where(mask == 0.0)
            assert len(indx) > 0
            assert len(indy) > 0

            incounty = mukey_map[(indx, indy)]

            # find the centroid of the county in case we need to use statsgo later on
            c_px, c_py = centroid_px(indx, indy)
            c_lng, c_lat = px_to_lnglat(transform, c_px, c_py, utmproj4, wgs84_proj4)
            assert c_lng > l
            assert c_lng < r
            assert c_lat > b
            assert c_lat < t

            # determine dominate mukey
            n = mask.shape[0]*mask.shape[1]
            print(incounty.shape, n, incounty.shape[0]/n)
            counter = Counter(incounty)
            dom_mukey = None
            for k, cnt in counter.most_common():
                if k != 0.0:
                    dom_mukey = int(k)
                    break
            print('mukey', dom_mukey)

            # if we succeeded store mukey to file
            fp.write('{STATEFP},{COUNTYFP},{COUNTYNS},{AFFGEOID},{GEOID}'
                     ',{NAME},{LSAD},{ALAND},{AWATER},{mukey},{c_lng},{c_lat}\n'
                     .format(**record, mukey=dom_mukey, c_lng=c_lng, c_lat=c_lat))

        except:
            fpe.write('{AFFGEOID}\n'.format(**record))

    fp.close()
    fpe.close()
