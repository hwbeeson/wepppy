import os

from os.path import exists as _exists
from os.path import join as _join
from os.path import split as _split

import sys
import shutil
from glob import glob
from wepppy.nodb import Ron, Wepp
from wepppy.wepp.stats import HillSummary, ChannelSummary, OutletSummary, SedimentDelivery

os.chdir('/geodata/weppcloud_runs/')

if __name__ == "__main__":
    prefix = 'lt2021_1'
    outdir = '/home/mariana/%s_csvs' % prefix

    if _exists(outdir):
        res = input('Outdir exists, Delete outdir?')
        if not res.lower().startswith('y'):
            sys.exit()

        shutil.rmtree(outdir)

    os.mkdir(outdir)

    scenarios = [
                 '202012.SimFire_fccsFuels_obs_cli',
                 '202012.SimFire_landisFuels_obs_cli',
                 '202012.SimFire_landisFuels_fut_cli_A2',
                 '202012.CurCond',
                 '202012.PrescFire',
                 '202012.LowSev',
                 '202012.ModSev',
                 '202012.HighSev',
                 '202012.Thinn96',
                 '202012.Thinn93',
                 '202012.Thinn85'
                ]

    wds = []
    for wc in scenarios:
        wds.extend(glob(_join('/geodata/weppcloud_runs', '*{}*'.format(wc))))
    wds = [wd for wd in wds if os.path.isdir(wd)]

    fp_hill = open(_join(outdir, '%s_hill_summary.csv' % prefix), 'w')
    fp_chn = open(_join(outdir, '%s_chn_summary.csv' % prefix), 'w')
    fp_out = open(_join(outdir, '%s_out_summary.csv' % prefix), 'w')
    fp_sd = open(_join(outdir, '%s_sed_del_summary.csv' % prefix), 'w')

    for i, wd in enumerate(wds):
        if not os.path.isdir(wd):
            continue
        print(wd)
        write_header = i == 0

        ron = Ron.getInstance(wd)
        subcatchments_summary = {_d['meta']['topaz_id']: _d for _d in ron.subs_summary()}
        channels_summary = {_d['meta']['topaz_id']: _d for _d in ron.chns_summary()}

        name = ron.name

        _wd = _split(wd)[-1].split('_')
        if _wd[3][0] in 'BWG' or _wd[3].startswith('Me'):
            indx = 4
        else:
            indx = 3

        scenario = '_'.join(_wd[indx:])
        watershed = '_'.join(_wd[:indx])

        run_descriptors = [('ProjectName', name), ('Scenario', scenario.replace('chn_cs25', '')
                                                                       .replace('chn_cs10', '')
                                                                       .replace('chn_cs30', '')
                                                                       .replace('chn_cs75', '')
                                                                       .replace('_', '')), ('Watershed', watershed)]

        loss = Wepp.getInstance(wd).report_loss()

        hill_rpt = HillSummary(loss, class_fractions=True, fraction_under=0.016, subs_summary=subcatchments_summary)

        chn_rpt = ChannelSummary(loss, chns_summary=channels_summary)
        out_rpt = OutletSummary(loss, fraction_under=0.016)
        sed_del = SedimentDelivery(wd)

        hill_rpt.write(fp_hill, write_header=write_header, run_descriptors=run_descriptors)
        chn_rpt.write(fp_chn, write_header=write_header, run_descriptors=run_descriptors)
        out_rpt.write(fp_out, write_header=write_header, run_descriptors=run_descriptors)
        sed_del.write(fp_sd, write_header=write_header, run_descriptors=run_descriptors)

    fp_hill.close()
    fp_chn.close()
    fp_out.close()
    fp_sd.close()
