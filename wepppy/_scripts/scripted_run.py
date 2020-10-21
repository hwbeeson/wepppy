import os
import shutil
from os.path import exists as _exists
from pprint import pprint
from time import time
from time import sleep

import wepppy
from wepppy.nodb import *
from os.path import join as _join
from wepppy.wepp.out import TotalWatSed

from osgeo import gdal, osr
gdal.UseExceptions()

if __name__ == '__main__':
    projects = [
        # dict(wd='SimFire_Watershed_1',
        #              extent=[-120.25497436523439, 39.072244930479926, -120.0146484375, 39.25857565711887],
        #              map_center=[-120.1348114013672, 39.165471994238374],
        #              map_zoom=12,
        #              outlet=[-120.09757304843217, 39.19773527084747],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_2',
        #              extent=[-120.25497436523439, 39.072244930479926, -120.0146484375, 39.25857565711887],
        #              map_center=[-120.1348114013672, 39.165471994238374],
        #              map_zoom=12,
        #              outlet=[-120.11460381632118, 39.18896973503106],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_3',
        #              extent=[-120.25497436523439, 39.072244930479926, -120.0146484375, 39.25857565711887],
        #              map_center=[-120.1348114013672, 39.165471994238374],
        #              map_zoom=12,
        #              outlet=[-120.12165282292143, 39.18644160172608],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_4',
        #              extent=[-120.20605087280275, 39.15083019711799, -120.08588790893556, 39.243953257043124],
        #              map_center=[-120.14596939086915, 39.19740715574304],
        #              map_zoom=13,
        #              outlet=[-120.12241504431637, 39.181379503672105],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_5',
        #              extent=[-120.25222778320314, 39.102091011833686, -120.01190185546876, 39.28834275351453],
        #              map_center=[-120.13206481933595, 39.19527859633793],
        #              map_zoom=12,
        #              outlet=[-120.1402884859731, 39.175919130374645],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_6',
        #              extent=[-120.25222778320314, 39.102091011833686, -120.01190185546876, 39.28834275351453],
        #              map_center=[-120.13206481933595, 39.19527859633793],
        #              map_zoom=12,
        #              outlet=[-120.14460408169862, 39.17224134827233],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_7_Ward',
        #              extent=[-120.29445648193361, 39.06424830007589, -120.11867523193361, 39.20059987393997],
        #              map_center=[-120.20656585693361, 39.13245708812353],
        #              map_zoom=12,
        #              outlet=[-120.15993239840523, 39.13415744093873],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_8',
        #              extent=[-120.29102325439453, 39.02451827974919, -120.11524200439455, 39.16094667321639],
        #              map_center=[-120.20313262939455, 39.09276546806873],
        #              map_zoom=12,
        #              outlet=[-120.16237493339143, 39.12864047715305],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_9_Blackwood',
        #              extent=[-120.29102325439453, 39.02451827974919, -120.11524200439455, 39.16094667321639],
        #              map_center=[-120.20313262939455, 39.09276546806873],
        #              map_zoom=12,
        #              outlet=[-120.16359931397338, 39.10677866737716],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_10',
        #              extent=[-120.29102325439453, 39.02451827974919, -120.11524200439455, 39.16094667321639],
        #              map_center=[-120.20313262939455, 39.09276546806873],
        #              map_zoom=12,
        #              outlet=[-120.14140904093959, 39.07218260362715],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_11_General',
        #              extent=[-120.23197174072267, 38.9348437659246, -120.05619049072267, 39.07144530820888],
        #              map_center=[-120.14408111572267, 39.003177506910475],
        #              map_zoom=12,
        #              outlet=[-120.12006459240162, 39.05139598278608],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_12_Meeks',
        #              extent=[-120.23197174072267, 38.9348437659246, -120.05619049072267, 39.07144530820888],
        #              map_center=[-120.14408111572267, 39.003177506910475],
        #              map_zoom=12,
        #              outlet=[-120.12452021800915, 39.036407051851995],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_13',
        #              extent=[-120.23197174072267, 38.9348437659246, -120.05619049072267, 39.07144530820888],
        #              map_center=[-120.14408111572267, 39.003177506910475],
        #              map_zoom=12,
        #              outlet=[-120.11884807004954, 39.02163646138702],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #       dict(wd='SimFire_Watershed_14',
        #            extent=[-120.23197174072267, 38.9348437659246, -120.05619049072267, 39.07144530820888],
        #            map_center=[-120.14408111572267, 39.003177506910475],
        #            map_zoom=12,
        #            outlet=[-120.12066635447759, 39.01951924517021],
        #            landuse=None,
        #            cs=50, erod=0.000001),
                dict(wd='SimFire_Watershed_15',
                     extent=[-120.15652656555177, 38.98636711600028, -120.09644508361818, 39.033052785617535],
                     map_center=[-120.12648582458498, 39.00971380270266],
                     map_zoom=14,
                     outlet=[-120.10916060023823, 39.004865203316534],
                     landuse=None,
                     cs=50, erod=0.000001, chn_chn_wepp_width=1.0),
        #         dict(wd='SimFire_Watershed_16',
        #              extent=[-120.23197174072267, 38.9348437659246, -120.05619049072267, 39.07144530820888],
        #              map_center=[-120.14408111572267, 39.003177506910475],
        #              map_zoom=12,
        #              outlet=[-120.10472536830764, 39.002638030718146],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_17',
        #              extent=[-120.23197174072267, 38.9348437659246, -120.05619049072267, 39.07144530820888],
        #              map_center=[-120.14408111572267, 39.003177506910475],
        #              map_zoom=12,
        #              outlet=[-120.10376442165887, 39.00072228304711],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_18',
        #              extent=[-120.22579193115236, 38.826603057341515, -119.98546600341798, 39.01358193815758],
        #              map_center=[-120.10562896728517, 38.92015408680781],
        #              map_zoom=12,
        #              outlet=[-120.10700793337516, 38.95312733140358],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_19',
        #              extent=[-120.22579193115236, 38.826603057341515, -119.98546600341798, 39.01358193815758],
        #              map_center=[-120.10562896728517, 38.92015408680781],
        #              map_zoom=12,
        #              outlet=[-120.09942499965612, 38.935371421937056],
        #              landuse=None,
        #              cs=50, erod=0.000001),
        #         dict(wd='SimFire_Watershed_20',
        #             extent=[-120.14305114746095, 38.877536817489165, -120.02288818359376, 38.97102081360566],
        #             map_center=[-120.08296966552736, 38.924294213302424],
        #             map_zoom=13,
        #             outlet=[-120.07227563388808, 38.940891230590054],
        #             landuse=None,
        #             cs=50, erod=0.000001)
                 ]
    for proj in projects:
        wd = proj['wd']
        extent = proj['extent']
        map_center = proj['map_center']
        map_zoom = proj['map_zoom']
        outlet = proj['outlet']
        default_landuse = proj['landuse']

        if _exists(wd):
            shutil.rmtree(wd)
        os.mkdir(wd)

        #ron = Ron(wd, "lt-fire.cfg")
        ron = Ron(wd, "lt.cfg")
        #ron = Ron(wd, "0.cfg")
        ron.name = wd
        ron.set_map(extent, map_center, zoom=map_zoom)
        ron.fetch_dem()

        topaz = Topaz.getInstance(wd)
        topaz.build_channels(csa=5, mcl=60)
        topaz.set_outlet(*outlet)
        sleep(0.5)
        topaz.build_subcatchments()

        wat = Watershed.getInstance(wd)
        wat.abstract_watershed(chn_wepp_width=proj['chn_chn_wepp_width'])
        translator = wat.translator_factory()
        topaz_ids = [top.split('_')[1] for top in translator.iter_sub_ids()]

        landuse = Landuse.getInstance(wd)
        landuse.mode = LanduseMode.Gridded
        landuse.build()
        landuse = Landuse.getInstance(wd)

        # 105 - Tahoe High severity fire
        # topaz_ids is a list of string ids e.g. ['22', '23']
        if default_landuse is not None:
            landuse.modify(topaz_ids, default_landuse)

        soils = Soils.getInstance(wd)
        soils.mode = SoilsMode.Gridded
        soils.build()

        climate = Climate.getInstance(wd)
        stations = climate.find_closest_stations()
        climate.input_years = 27
        climate.climatestation = stations[0]['id']

        climate.climate_mode = ClimateMode.Observed
        climate.climate_spatialmode = ClimateSpatialMode.Multiple
        climate.set_observed_pars(start_year=1990, end_year=2016)

        climate.build(verbose=1)

        wepp = Wepp.getInstance(wd)
        wepp.prep_hillslopes()
        wepp.run_hillslopes()

        wepp = Wepp.getInstance(wd)
        wepp.prep_watershed(erodibility=proj['erod'], critical_shear=proj['cs'])
        wepp.run_watershed()
        loss_report = wepp.report_loss()

        fn = _join(ron.export_dir, 'totalwatsed.csv')

        totwatsed = TotalWatSed(_join(ron.output_dir, 'totalwatsed.txt'),
                                wepp.baseflow_opts, wepp.phosphorus_opts)
        totwatsed.export(fn)
        assert _exists(fn)

        print(loss_report.out_tbl)