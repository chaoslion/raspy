# -*- coding: utf-8 -*-
from math import fsum
from raspysystem.raspytask import RasPyTask
from raspysystem.raspysamplelogger import RasPySampleLogger
from raspysystem.raspyenergymeter import RasPyEnergyMeter

class SupplyTask(RasPyTask):
    SUPPLY_OK = 0
    SUPPLY_HI = 1
    SUPPLY_LO = 2
    GOOD_SUPPLY = [
        [4.95, 5.05],
        [0.20, 0.30]
    ]

    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "supply")

        maxlogs = self.kernel().get_updates24h()
        windows = [5, 15, 60]
        self._vlog = RasPySampleLogger(maxlogs, windows)
        self._ilog = RasPySampleLogger(maxlogs, windows)
        self._plog = RasPySampleLogger(maxlogs, windows)

        self._energy_meter = RasPyEnergyMeter(
            self.period(),
            self.kernel().get_databasepath(),
            "supply"
        )

    def get_vlog(self):
        return self._vlog

    def get_ilog(self):
        return self._ilog

    def get_plog(self):
        return self._plog

    # this has to match with self.WINDOWS
    # > 60 is in the 2nd place in array!
    # returns array of [numeric, state] for the 3 supply values
    def get_hourly_stats(self):
        result = [
            [self._vlog.get_averages()[2], self.SUPPLY_OK],
            [self._ilog.get_averages()[2], self.SUPPLY_OK],
            [self._plog.get_averages()[2], self.SUPPLY_OK]
        ]

        # test if voltage and current are valid
        for i in range(2):
            avg = result[i][0]
            if avg < self.GOOD_SUPPLY[i][0]:
                result[i][1] = self.SUPPLY_LO
            elif avg > self.GOOD_SUPPLY[i][1]:
                result[i][1] = self.SUPPLY_HI

        return result

    def run_event(self):
        time = self.time()

        # log most recent value => average over last tick periods
        # v, i, p = self.kernel().get_supply().read()
        samples = self.kernel().get_supply().get_samples()
        # average over tick period
        v = fsum(samples[0]) / len(samples[0])
        i = fsum(samples[1]) / len(samples[1])
        p = fsum(samples[2]) / len(samples[2])

        self._vlog.log(time.jstimestamp(), v)
        self._ilog.log(time.jstimestamp(), i)
        self._plog.log(time.jstimestamp(), p)

        self._energy_meter.update(time, p)
        return True

    def report_event(self):
        return dict(
            energy=self._energy_meter.serialize(),
            voltage=self._vlog.serialize(),
            current=self._ilog.serialize(),
            power=self._plog.serialize()
        )

    def startup_event(self, db, cfg):
        return True

    # def backup_event(self, db):
    #     time = self.time()
    #     self._energy_meter.store(time, db)
