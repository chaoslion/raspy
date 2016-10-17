# -*- coding: utf-8 -*-
import util
from raspysystem.raspytask import RasPyTask
from raspytasks.fritz.landevice import LanDevice

class StatsTask(RasPyTask):

    STAT_COUNT = 0
    STAT_MEAN = 1

    TYPE_HOUR = 0x0001
    TYPE_DAY = 0x0002
    TYPE_WEEK = 0x0004
    TYPE_MONTH = 0x0008
    TYPE_ALL = (
        TYPE_HOUR |
        TYPE_DAY |
        TYPE_WEEK |
        TYPE_MONTH
    )

    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "statistics")

        self._stats_hour = list()
        self._stats_day = list()
        self._stats_week = list()
        self._stats_month = list()

    def find_stat_by_name(self, name, stats):
        for stat in stats:
            if stat.get_name() == name:
                return stat
        return None

    def find_stat(self, name, ttype):
        stats = list()

        if ttype & self.TYPE_HOUR:
            stats.append(self.find_stat_by_name(name, self._stats_hour))
        if ttype & self.TYPE_DAY:
            stats.append(self.find_stat_by_name(name, self._stats_day))
        if ttype & self.TYPE_WEEK:
            stats.append(self.find_stat_by_name(name, self._stats_week))
        if ttype & self.TYPE_MONTH:
            stats.append(self.find_stat_by_name(name, self._stats_month))

        return stats

    def _add_stat(self, name, stype, ttype):

        if stype == self.STAT_COUNT:
            stat = util.StatsCount(name)
        elif stype == self.STAT_MEAN:
            stat = util.StatsMean(name)

        if ttype & self.TYPE_HOUR:
            self._stats_hour.append(stat)
        if ttype & self.TYPE_DAY:
            self._stats_day.append(stat)
        if ttype & self.TYPE_WEEK:
            self._stats_week.append(stat)
        if ttype & self.TYPE_MONTH:
            self._stats_month.append(stat)

    def _update_fritz(self):
        fdm = self.find_worker("fritz").get_devicemanager()
        mobiles = fdm.find_by_type(LanDevice.TYPE_MOBILE)
        for m in mobiles:
            name = "fritz." + m.get_owner() + ".mobile"

            stats = self.find_stat(name + ".on", self.TYPE_ALL)
            for stat in stats:
                stat.update(1 if m.get_state() else 0)

            stats = self.find_stat(name + ".off", self.TYPE_ALL)
            for stat in stats:
                stat.update(1 if not m.get_state() else 0)

    def _update_supply(self):
        supply = self.find_worker("supply")
        vip = [
            ["voltage", supply.get_voltage()],
            ["current", supply.get_current()],
            ["power", supply.get_power()]
        ]

        for x in vip:
            stats = self.find_stat("supply." + x[0], self.TYPE_ALL)
            for stat in stats:
                stat.update(x[1].get_samples_value())

    def startup(self, db, cfg):
        # supply
        self._add_stat("supply.voltage", self.STAT_MEAN, self.TYPE_ALL)
        self._add_stat("supply.current", self.STAT_MEAN, self.TYPE_ALL)
        self._add_stat("supply.power", self.STAT_MEAN, self.TYPE_ALL)

        # fritz
        fdm = self.find_worker("fritz").get_devicemanager()
        mobiles = fdm.find_devices_by_type(LanDevice.TYPE_MOBILE)
        for m in mobiles:
            name = "fritz." + m.get_owner() + ".mobile"
            self._add_stat(name + ".on", self.STAT_COUNT, self.TYPE_ALL)
            self._add_stat(name + ".off", self.STAT_COUNT, self.TYPE_ALL)

        return True

    def run(self):
        self._update_supply()
        self._update_fritz()
        return True
