from os.path import join as _join
from os.path import exists as _exists
from glob import glob
from collections import OrderedDict

from wepppy.all_your_base import parse_units, parse_name, RowData

from wepppy.wepp.out import Loss
from .report_base import ReportBase


class HillSummary(ReportBase):
    def __init__(self, loss: Loss):
        self.data = loss.hill_tbl

        self.header = (
            'WeppID',
            'TopazID',
            'Landuse',
            'Soil',
            'Length (m)',
            'Hillslope Area (ha)',
            'Runoff (mm)',
            'Subrunoff (mm)',
            'Baseflow Volume (m^3)',
            'Soil Loss Density (kg/ha)',
            'Sediment Deposition Density (kg/ha)',
            'Sediment Yield Density (kg/ha)',
            'Solub. React. P Density (kg/ha)',
            'Particulate P Density (kg/ha)',
            'Total P Density (kg/ha)'
        )

    def __iter__(self):
        data = self.data
        for i in range(len(data)):
            yield RowData(OrderedDict([(colname, data[i][parse_name(colname)]) for colname in self.header]))


class ChannelSummary(ReportBase):
    def __init__(self, loss: Loss):
        self.data = loss.chn_tbl

        self.header = (
            'WeppID',
            'TopazID',
            'Length (m)',
            'Area (ha)',
            'Discharge Volume (m^3)',
            'Sediment Yield (tonne)',
            'Soil Loss (kg)',
            'Upland Charge (m^3)',
            'Subsuface Volume (m^3)',
            'Flow Phosphorus (m^3)',
            'Solub. React. P Density (kg/ha)',
            'Particulate P Density (kg/ha)',
            'Total P Density (kg/ha)'
        )

    def __iter__(self):
        data = self.data
        for i in range(len(data)):
            yield RowData(OrderedDict([(colname, data[i][parse_name(colname)]) for colname in self.header]))


class OutletSummary(ReportBase):
    def __init__(self, loss: Loss):
        self.data = loss.out_tbl

    def __iter__(self):
        for d in self.data:
            if d['units'] is None:
                name = '{0[key]}'.format(d)
            else:
                name = '{0[key]} ({0[units]})'.format(d)

            value = d['v']
            units = d['units']

            yield name, value, units


if __name__ == "__main__":

    loss = Loss('/geodata/weppcloud_runs/bb967f25-9fd6-4641-b737-bb10a1cf7843/wepp/output/loss_pw0.txt',
                '/geodata/weppcloud_runs/bb967f25-9fd6-4641-b737-bb10a1cf7843/')

    hill_rpt = HillSummary(loss)

    for row in hill_rpt:
        for k, v in row:
            print(k, v)

    chn_rpt = ChannelSummary(loss)

    for row in chn_rpt:
        for k, v in row:
            print(k, v)

    out_rpt = OutletSummary(loss)

    for name, value, units in out_rpt:
        print(name, value, units)