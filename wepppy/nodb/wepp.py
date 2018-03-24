# standard library
import os

from os.path import join as _join
from os.path import exists as _exists
from os.path import split as _split

from glob import glob

import shutil

# non-standard
import jsonpickle

# wepppy
from wepppy.wepp.runner import (
    make_hillslope_run,
    run_hillslope,
    make_watershed_run,
    run_watershed
)
from wepppy.wepp.management import (
    get_channel,
    merge_managements,
)

from wepppy.all_your_base import isfloat
from wepppy.wepp.out import LossReport, EbeReport

# wepppy submodules
from .base import NoDbBase, TriggerEvents
from .landuse import Landuse, LanduseMode
from .soils import Soils, SoilsMode
from .climate import Climate, ClimateMode
from .watershed import Watershed


class BaseflowOpts(object):
    def __init__(self):
        """
        Stores the coeffs that go into gwcoeff.txt
        """
        # Initial groundwater storage (mm)
        self.gwstorage = 200 
        
        # Baseflow coefficient (per day)
        self.bfcoeff = 0.04

        # Deep seepage coefficient (per day)        
        self.dscoeff = 0 
        
        # Watershed groundwater baseflow threshold area (ha)
        self.bfthreshold = 1 

    def parse_inputs(self, kwds):
        self.gwstorage = float(kwds['gwstorage'])
        self.bfcoeff = float(kwds['bfcoeff'])
        self.dscoeff = float(kwds['dscoeff'])
        self.bfthreshold = float(kwds['bfthreshold'])
        
    @property
    def contents(self):
        return ( 
            '{0.gwstorage}\tInitial groundwater storage (mm)\n'
            '{0.bfcoeff}\tBaseflow coefficient (per day)\n'
            '{0.dscoeff}\tDeep seepage coefficient (per day)\n'
            '{0.bfthreshold}\tWatershed groundwater baseflow threshold area (ha)\n\n'
            .format(self) 
        )


def validate_phosphorus_txt(fn):

    with open(fn) as fp:
        lines = fp.readlines()
    lines = [L for L in lines if not L.strip() == '']
    if 'Phosphorus concentration' != lines[0].strip():
        return False
     
    opts = [isfloat(L.split()[0]) for L in lines[1:]]
    if len(opts) != 4:
        return False
        
    if not all(opts):
        return False
        
    return True


class PhosphorusOpts(object):
    def __init__(self):
        # Surface runoff concentration (mg/l)
        self.surf_runoff = ''  # 0.0118000004441
        
        # Subsurface lateral flow concentration (mg/l)
        self.lateral_flow = ''  # 0.0109999999404
        
        # Baseflow concentration (mg/l)
        self.baseflow = ''  # 0.0196000002325
        
        # Sediment concentration (mg/kg)
        self.sediment = ''  # 1024

    def parse_inputs(self, kwds):
        # noinspection PyBroadException
        try:
            self.surf_runoff = float(kwds['surf_runoff'])
            self.lateral_flow = float(kwds['lateral_flow'])
            self.baseflow = float(kwds['baseflow'])
            self.sediment = float(kwds['sediment'])
        except Exception:
            pass
    
    @property
    def isvalid(self):
        return isfloat(self.surf_runoff) and \
               isfloat(self.lateral_flow) and \
               isfloat(self.baseflow) and \
               isfloat(self.sediment)
        
    @property
    def contents(self):
        return ( 
            'Phosphorus concentration\n'
            '{0.surf_runoff}\tSurface runoff concentration (mg/l)\n'
            '{0.lateral_flow}\tSubsurface lateral flow concentration (mg/l)\n'
            '{0.baseflow}\tBaseflow concentration (mg/l)\n'
            '{0.sediment}\tSediment concentration (mg/kg)\n\n'
            .format(self) 
        )

    def asdict(self):
        return dict(surf_runoff=self.surf_runoff,
                    lateral_flow=self.lateral_flow,
                    baseflow=self.baseflow,
                    sediment=self.sediment)


class WeppNoDbLockedException(Exception):
    pass


class Wepp(NoDbBase):
    __name__ = 'Wepp'

    def __init__(self, wd, cfg_fn):
        super(Wepp, self).__init__(wd, cfg_fn)

        self.lock()

        # noinspection PyBroadException
        try:
            wepp_dir = self.wepp_dir
            if not _exists(wepp_dir):
                os.mkdir(wepp_dir)

            self.clean()
            
            self.phosphorus_opts = PhosphorusOpts()
            self.baseflow_opts = BaseflowOpts()
                
            self.dump_and_unlock()

        except Exception:
            self.unlock('-f')
            raise
    #
    # Required for NoDbBase Subclass
    #

    # noinspection PyPep8Naming
    @staticmethod
    def getInstance(wd):
        with open(_join(wd, 'wepp.nodb')) as fp:
            db = jsonpickle.decode(fp.read())
            assert isinstance(db, Wepp)
            return db

    @property
    def _nodb(self):
        return _join(self.wd, 'wepp.nodb')

    @property
    def _lock(self):
        return _join(self.wd, 'wepp.nodb.lock')

    def parse_inputs(self, kwds):
        self.lock()

        # noinspection PyBroadException
        try:
            self.baseflow_opts.parse_inputs(kwds)
            self.phosphorus_opts.parse_inputs(kwds)
            
            self.dump_and_unlock()

        except Exception:
            self.unlock('-f')
            raise
            
    @property
    def has_run(self):
        output_dir = self.output_dir
        loss_pw0 = _join(output_dir, 'loss_pw0.txt')
        return _exists(loss_pw0)
    
    #
    # hillslopes
    #
    def prep_hillslopes(self):
    
        translator = Watershed.getInstance(self.wd).translator_factory()
        
        # get translator
        self._prep_slopes(translator)
        self._prep_managements(translator)
        self._prep_soils(translator)
        self._prep_climates(translator)
        self._make_hillslope_runs(translator)
        self._prep_frost()
        self._prep_phosphorus()
        self._prep_baseflow()
        
    def _prep_frost(self):
        fn = _join(self.runs_dir, 'frost.txt')
        with open(fn, 'w') as fp:
            fp.write('1  1  1\n')
            fp.write('1.0   1.0  1.0   0.5\n\n')
        
    def _prep_phosphorus(self):

        # noinspection PyMethodFirstArgAssignment
        self = self.getInstance(self.wd)
        
        fn = _join(self.runs_dir, 'phosphorus.txt')
        if self.phosphorus_opts.isvalid:
            with open(fn, 'w') as fp:
                fp.write(self.phosphorus_opts.contents)
        
        if _exists(fn):
            if not validate_phosphorus_txt(fn):
                os.remove(fn)
                
    def _prep_baseflow(self):
        fn = _join(self.runs_dir, 'gwcoeff.txt')
        with open(fn, 'w') as fp:
            fp.write(self.baseflow_opts.contents)
            
    def clean(self):
        runs_dir = self.runs_dir
        if not _exists(runs_dir):
            os.mkdir(runs_dir)
            
        output_dir = self.output_dir
        if not _exists(output_dir):
            os.mkdir(output_dir)
            
    def _prep_slopes(self, translator):
        watershed = Watershed.getInstance(self.wd)
        wat_dir = self.wat_dir
        runs_dir = self.runs_dir
        
        for topaz_id, _ in watershed.sub_iter():
            wepp_id = translator.wepp(top=int(topaz_id))
            
            src_fn = _join(wat_dir, 'hill_{}.slp'.format(topaz_id))
            dst_fn = _join(runs_dir, 'p%i.slp' % wepp_id)
            shutil.copyfile(src_fn, dst_fn)
            
    def _prep_managements(self, translator):
        landuse = Landuse.getInstance(self.wd)
        years = Climate.getInstance(self.wd).input_years
        runs_dir = self.runs_dir
        
        if landuse.mode == LanduseMode.Gridded:
            for topaz_id, man_summary in landuse.sub_iter():
                wepp_id = translator.wepp(top=int(topaz_id))
                dst_fn = _join(runs_dir, 'p%i.man' % wepp_id)
                
                management = man_summary.get_management()
                multi = management.build_multiple_year_man(years)
                fn_contents = str(multi)
                
                with open(dst_fn, 'w') as fp:
                    fp.write(fn_contents)
                
        else:
            raise NotImplementedError('Single landuse not implemented')
        
    def _prep_soils(self, translator):
        soils = Soils.getInstance(self.wd)
        soils_dir = self.soils_dir
        runs_dir = self.runs_dir

        for topaz_id, soil in soils.sub_iter():
            wepp_id = translator.wepp(top=int(topaz_id))
            src_fn = _join(soils_dir, soil.fname)
            dst_fn = _join(runs_dir, 'p%i.sol' % wepp_id)
            shutil.copyfile(src_fn, dst_fn)

    def _prep_climates(self, translator):
        watershed = Watershed.getInstance(self.wd)
        climate = Climate.getInstance(self.wd)
        cli_dir = self.cli_dir
        runs_dir = self.runs_dir
    
        if climate.climate_mode == ClimateMode.Localized:
            for topaz_id, cli_fn in climate.sub_cli_fns.items():
                wepp_id = translator.wepp(top=int(topaz_id))
                dst_fn = _join(runs_dir, 'p%i.cli' % wepp_id)
                cli_path = _join(cli_dir, cli_fn)
                shutil.copyfile(cli_path, dst_fn)
                
        else:
            for topaz_id, _ in watershed.sub_iter():
                wepp_id = translator.wepp(top=int(topaz_id))
                dst_fn = _join(runs_dir, 'p%i.cli' % wepp_id)
                cli_path = _join(cli_dir, climate.cli_fn)
                shutil.copyfile(cli_path, dst_fn)
                
    def _make_hillslope_runs(self, translator):
        watershed = Watershed.getInstance(self.wd)
        runs_dir = self.runs_dir
        years = Climate.getInstance(self.wd).input_years
        
        for topaz_id, _ in watershed.sub_iter():
            wepp_id = translator.wepp(top=int(topaz_id))
            
            make_hillslope_run(wepp_id, years, runs_dir)
            
    def run_hillslopes(self):
        translator = Watershed.getInstance(self.wd).translator_factory()
        watershed = Watershed.getInstance(self.wd)
        runs_dir = os.path.abspath(self.runs_dir)
        
        for topaz_id, _ in watershed.sub_iter():
            wepp_id = translator.wepp(top=int(topaz_id))
            assert run_hillslope(wepp_id, runs_dir)
     
    #
    # watershed
    #    
    def prep_watershed(self):
        watershed = Watershed.getInstance(self.wd)
        translator = watershed.translator_factory()

        print('prep_structure')
        self._prep_structure(translator)

        print('prep_channel_slopes')
        self._prep_channel_slopes()

        print('prep_channel_chn')
        self._prep_channel_chn(translator)

        print('prep_impoundment')
        self._prep_impoundment()

        print('prep_channel_soils')
        self._prep_channel_soils(translator)

        print('prep_channel_climate')
        self._prep_channel_climate(translator)

        print('prep_channel_input')
        self._prep_channel_input()

        print('prep_watershed_managements')
        self._prep_watershed_managements(translator)

        print('make_watershed_run')
        self._make_watershed_run(translator)

    def _prep_structure(self, translator):
        watershed = Watershed.getInstance(self.wd)
        structure = watershed.structure
        runs_dir = self.runs_dir
        
        s = ['99.1']
        for L in structure:
            s2 = "2    {} {} {}   "\
                 .format(*[translator.wepp(top=v) for v in L[1:4]])
                
            s2 += "{} {} {}   {} {} {}"\
                  .format(*[translator.wepp(top=v) for v in L[4:]])
#                .format(*[translator.chn_enum(top=v) for v in L[4:]])
                
            s.append(s2)
            
        with open(_join(runs_dir, 'pw0.str'), 'w') as fp:
            fp.write('\n'.join(s) + '\n')
            
    def _prep_channel_slopes(self):
        wat_dir = self.wat_dir
        runs_dir = self.runs_dir
        
        shutil.copyfile(_join(wat_dir, 'channels.slp'),
                        _join(runs_dir, 'pw0.slp'))
                        
    def _prep_channel_chn(self, translator):
        assert translator is not None

        watershed = Watershed.getInstance(self.wd)
        runs_dir = self.runs_dir
        
        chn_n = watershed.chn_n

        fp = open(_join(runs_dir, 'pw0.chn'), 'w')
        fp.write('99.1\r\n{chn_n}\r\n4\r\n1.500000\r\n'
                 .format(chn_n=chn_n))
        
        for topaz_id, chn_summary in watershed.chn_iter():
            chn_key = chn_summary.channel_type
            chn_d = get_channel(chn_key)
            contents = chn_d['contents']
            fp.write(contents)
            fp.write('\n')
        fp.close()
        
    def _prep_impoundment(self):
        runs_dir = self.runs_dir
        with open(_join(runs_dir, 'pw0.imp'), 'w') as fp:
            fp.write('99.1\n0\n')

    def _prep_channel_input(self):

        wat = Watershed.getInstance(self.wd)
        chn_n = wat.chn_n
        sub_n = wat.sub_n
        total = chn_n + sub_n

        runs_dir = self.runs_dir
        with open(_join(runs_dir, 'chan.inp'), 'w') as fp:
            fp.write('1 600\n0\n1\n{}\n'.format(total))


    def _prep_channel_soils(self, translator):
        soils = Soils.getInstance(self.wd)
        soils_dir = self.soils_dir
        runs_dir = self.runs_dir
        
        chn_n = Watershed.getInstance(self.wd).chn_n
        
        # build list of soils
        soil_c = []
        for topaz_id, soil in soils.chn_iter():
            soil_c.append((translator.chn_enum(top=int(topaz_id)), soil))
        soil_c.sort(key=lambda x: x[0])
        
        versions = []
        for chn_enum, soil in soil_c:
            soil_fn = _join(soils_dir, soil.fname)
            lines = open(soil_fn).readlines()
            version = lines[0].replace('#', '').strip()
            versions.append(version)
            
        versions = set(versions)
        if len(versions) > 1:
            raise Exception('Do not know how to merge '
                            'soils of different versions')

        if len(versions) == 0:
            raise Exception('Could not find any soils for channels.')

        version = versions.pop()
            
        if '7778' in version:
            # iterate over soils and append them together
            fp = open(_join(runs_dir, 'pw0.sol'), 'w')
            fp.write('7778.0\ncomments: soil file\n{chn_n} 1\n'
                     .format(chn_n=chn_n))
            i = 0
            for chn_enum, soil in soil_c:
                soil_fn = _join(soils_dir, soil.fname)
                lines = open(soil_fn).readlines()
                for i, line in enumerate(lines):
                    line = ''.join([v.strip() for v in line.split()])
                    if line == '11':
                        break
                        
#                fp.write(''.join(lines[i+1:]) + '\n')
                fp.write("""\
Bidart_1 MPM 1 0.02 0.75 4649000 0.20854 100.000
400	1.5	0.5	1	0.242	0.1145	66.8	7	3	11.3	20
1 10000 0.0001
""")
                    
            fp.close()
            
        else:
            # iterate over soils and append them together
            fp = open(_join(runs_dir, 'pw0.sol'), 'w')
            fp.write('2006.2\ncomments: soil file\n{chn_n} 1\n'
                     .format(chn_n=chn_n))
            for chn_enum, soil in soil_c:
                soil_fn = _join(soils_dir, soil.fname)
                lines = open(soil_fn).readlines()
                lines = [line for line in lines if not line.strip().startswith('#')]
                        
                fp.write(''.join(lines[3:6]))
                    
            fp.close()
        
    def _prep_watershed_managements(self, translator):
        landuse = Landuse.getInstance(self.wd)
        runs_dir = self.runs_dir
    
        years = Climate.getInstance(self.wd).input_years

        """
        # build list of managements
        mans_c = []
        for topaz_id, man in landuse.chn_iter():
            man_obj = get_management(man.key)
            chn_enum = translator.chn_enum(top=int(topaz_id))
            mans_c.append((chn_enum, man_obj))
            
        # sort list of (chn_enum, Management) by chn_enum
        mans_c.sort(key=lambda x: x[0]) 
        mans_c = [v for k, v in mans_c]  # <- list of Management
        
        if len(mans_c) > 1:
            chn_man = merge_managements(mans_c)
        else:
            chn_man = mans_c[0]
            
        """
        keys = [man.key for topaz_id, man in landuse.chn_iter()]
        from collections import Counter
        mankey = Counter(keys).most_common()[0][0]

        chn_man = landuse.managements[str(mankey)].get_management()
        chn_man.make_multiple_ofe(len(keys))

        if years > 1:
            multi = chn_man.build_multiple_year_man(years)
            fn_contents = str(multi)
        else:
            fn_contents = str(chn_man)

        with open(_join(runs_dir, 'pw0.man'), 'w') as fp:
            fp.write(fn_contents)

    def _prep_channel_climate(self, translator):
        assert translator is not None

        runs_dir = self.runs_dir
        climate = Climate.getInstance(self.wd)
        dst_fn = _join(runs_dir, 'pw0.cli')
        cli_path = _join(self.cli_dir, climate.cli_fn)
        shutil.copyfile(cli_path, dst_fn)
    
    def _make_watershed_run(self, translator):
        runs_dir = self.runs_dir
        wepp_ids = list(translator.iter_wepp_sub_ids())
        wepp_ids.sort()
        years = Climate.getInstance(self.wd).input_years
        make_watershed_run(years, wepp_ids, runs_dir)
        
    def run_watershed(self):
        runs_dir = self.runs_dir
        assert run_watershed(runs_dir)

        for fn in glob(_join(self.runs_dir, '*.out')):
            dst_path = _join(self.output_dir, _split(fn)[1])
            shutil.move(fn, dst_path)

    def report_loss(self):
        output_dir = self.output_dir
        loss_pw0 = _join(output_dir, 'loss_pw0.txt')
        return LossReport(loss_pw0)

    def report_ebe(self):
        output_dir = self.output_dir
        loss_pw0 = _join(output_dir, 'loss_pw0.txt')
        loss_rpt = LossReport(loss_pw0)

        ebe_pw0 = _join(output_dir, 'ebe_pw0.txt')
        ebe_rpt = EbeReport(ebe_pw0)
        ebe_rpt.run_return_periods(loss_rpt)
        return  ebe_rpt

    def query_sub_phosphorus(self):
        wd = self.wd
        translator = Watershed.getInstance(wd).translator_factory()
        output_dir = self.output_dir
        loss_pw0 = _join(output_dir, 'loss_pw0.txt')
        report = LossReport(loss_pw0)
        
        d = {}
        for row in report.hill_tbl:
            topaz_id = translator.top(wepp=row['Hillslopes'])
            d[str(topaz_id)] = dict(
                topaz_id=topaz_id,
                total_p=row['Total Phosphorus']
            )
        
        return d
        
    def query_sub_runoff(self):
        wd = self.wd
        translator = Watershed.getInstance(wd).translator_factory()
        output_dir = self.output_dir
        loss_pw0 = _join(output_dir, 'loss_pw0.txt')
        report = LossReport(loss_pw0)
        
        d = {}
        for row in report.hill_tbl:
            topaz_id = translator.top(wepp=row['Hillslopes'])
            d[str(topaz_id)] = dict(
                topaz_id=topaz_id,
                runoff=row['Subrunoff Volume']
            )
        
        return d
    
    def query_sub_loss(self):
        wd = self.wd
        translator = Watershed.getInstance(wd).translator_factory()
        output_dir = self.output_dir
        loss_pw0 = _join(output_dir, 'loss_pw0.txt')
        report = LossReport(loss_pw0)
        
        d = {}
        for row in report.hill_tbl:
            topaz_id = translator.top(wepp=row['Hillslopes'])
            d[str(topaz_id)] = dict(
                topaz_id=topaz_id,
                v=row['Soil Loss']
            )
        
        return d
