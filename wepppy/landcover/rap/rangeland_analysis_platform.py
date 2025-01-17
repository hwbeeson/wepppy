from os.path import join as _join
from os.path import split as _split
from os.path import exists as _exists
import utm
import subprocess
import os
from enum import IntEnum
from glob import glob
import math

import numpy as np
import rasterio

from wepppy.all_your_base.geo import read_raster

IS_WINDOWS = os.name == 'nt'

_thisdir = os.path.dirname(__file__)

class RangelandAnalysisPlatformV2(object):
    def __init__(self, wd='.', bbox=None, cellsize=30):
        self.wd = wd
        self.bbox = bbox
        self.ds = {}
        self.cellsize = cellsize
        self.proj4 = None

        rap_fns = glob(_join(wd, '_rap_v2*.tif'))
        for rap_fn in rap_fns:
            head, tail = _split(rap_fn)
            year = int(tail.replace('_rap_v2_', '').replace('.tif', ''))
            self.ds[year] = rap_fn

    def retrieve(self, years):
        cellsize = self.cellsize
        bbox = self.bbox

        ul_x, ul_y, utm_number, utm_letter = utm.from_latlon(bbox[3], bbox[0])
        lr_x, lr_y, _, _ = utm.from_latlon(bbox[1], bbox[2], 
                                       force_zone_number=utm_number)
        proj4 = "+proj=utm +zone={zone} +{hemisphere} +datum=WGS84 +ellps=WGS84" \
            .format(zone=utm_number, hemisphere=('south', 'north')[bbox[3] > 0])

        for year in years:
            dst_fn = _join(self.wd, f'_rap_v2_{year}.tif')

            cmd = ['gdalwarp', 
                   '-co', 'compress=lzw', 
                   '-co', 'tiled=yes', 
                   '-co', 'bigtiff=yes',
                   '-t_srs', proj4,
                   '-te', str(ul_x), str(lr_y), str(lr_x), str(ul_y),
                   '-r', 'near',
                   '-tr', str(cellsize), str(cellsize),
                   f'/vsicurl/http://rangeland.ntsg.umt.edu/data/rap/rap-vegetation-cover/v2/vegetation-cover-v2-{year}.tif',
                   dst_fn]

            if _exists(dst_fn):
                os.remove(dst_fn)

            # run command, check_output returns standard output
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, errors = p.communicate(input=('0\n', '0\r\n')[IS_WINDOWS], timeout=15)

            if not _exists(dst_fn):
                raise Exception((cmd, output, errors))

            self.ds[year] = dst_fn

        self.proj4 = proj4
        self.ul_x, self.ul_y = ul_x, ul_y
        self.lr_x, self.lr_y = lr_x, lr_y

    def get_dataset(self, year):
        if year not in self.ds:
            self.retrieve([year])

        return RangelandAnalysisPlatformV2Dataset(self.ds[year])

    def _attribution(self):
        readme_txt = _join(self.wd, 'rap_readme.txt')
        if not _exists(readme_txt):
            os.copyfile(_join(_thisdir, 'rap_readme.txt', readme_txt))



class RAP_Band(IntEnum):
    ANNUAL_FORB_AND_GRASS = 1
    BARE_GROUND = 2
    LITTER = 3
    PERENNIAL_FORB_AND_GRASS = 4
    SHRUB = 5
    TREE = 6
    ANNUAL_FORB_AND_GRASS_UNCERTAINTY = 7
    BARE_GROUND_UNCERTAINTY = 8
    LITTER_UNCERTAINTY = 9
    PERRENIAL_FORB_AND_GRASS_UNCERTAINTY = 10
    SHRUB_UNCERTAINTY = 11
    TREE_UNCERTAINTY = 12


class RangelandAnalysisPlatformV2Dataset(object):
    def __init__(self, fn):
        self.ds = rasterio.open(fn)    


    def get_band(self, band: RAP_Band):
        data =  self.ds.read(band)
        return np.ma.masked_values(data, 65535)

    def _get_median(self, band: RAP_Band, indices):
        data = self.get_band(band)
        x = data[indices]

        retval = float(np.ma.median(x))
        if math.isnan(retval):
            return None

        return retval

    def spatial_aggregation(self, band: RAP_Band, subwta_fn):
        assert _exists(subwta_fn)
        subwta, transform, proj = read_raster(subwta_fn, dtype=np.int32)
        _ids = sorted(list(set(subwta.flatten())))

        domlc_d = {}
        for _id in _ids:
            if _id == 0:
                continue

            _id = int(_id)
            indices = np.where(subwta == _id)
            dom = self._get_median(band, indices)

            domlc_d[str(_id)] = dom
        return domlc_d

    def spatial_stats(self, band: RAP_Band, bound_fn):
        assert _exists(bound_fn)
        bounds, transform, proj = read_raster(bound_fn, dtype=np.int32)
        indices = np.where(bounds == 1)

        data = self.get_band(band)
        x = data[indices]

        return dict(num_pixels=len(indices[0]),
                    valid_pixels=len(indices[0]) - np.sum(x.mask),
                    mean=np.mean(x),
                    std=np.std(x),
                    units='%')


if __name__ == "__main__":
    bbox = [-114.63661319270066,45.41139471986449,-114.60663682475024,45.43207316134328]
    rap = RangelandAnalysisPlatformV2(wd='test', bbox=bbox)
    rap_ds = rap.get_dataset(2020)
    litter = rap_ds.get_band(RAP_Band.LITTER)
    print(litter)
     


