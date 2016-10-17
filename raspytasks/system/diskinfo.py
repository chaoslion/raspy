# -*- coding: utf-8 -*-
import psutil
from raspysystem.raspytask import RasPyTask, RasPySimpleTask
from raspysystem.raspydatarate import RasPyByteRate

class DiskInfoTask(RasPySimpleTask):

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "disk")

        self._partition = None
        self.total = 0
        self.used = 0
        self.free = 0

        self.write_count = 0
        self.write_time = 0
        self.read_count = 0
        self.read_time = 0

        maxlogs = self.kernel().get_updates24h()
        self.write_rate = RasPyByteRate(self.period(), maxlogs)
        self.read_rate = RasPyByteRate(self.period(), maxlogs)

    def startup_event(self, db, cfg):
        if not self._config_expect(["rootpartition"], cfg):
            return False
        self._partition = cfg["rootpartition"]
        return True

    def run_event(self):
        timestamp = self.time().jstimestamp()

        ioinfo = psutil.disk_io_counters(True)

        cnts = ioinfo[self._partition]
        usage = psutil.disk_usage('/')

        self.total = usage.total
        self.used = usage.used
        self.free = usage.free

        self.write_time = cnts.write_time
        self.write_count = cnts.write_count

        self.read_time = cnts.read_time
        self.read_count = cnts.read_count

        self.write_rate.log(timestamp, cnts.write_bytes)
        self.read_rate.log(timestamp, cnts.read_bytes)

        return True

    def report_event(self):
        return dict(
            total=self.total,
            used=self.used,
            free=self.free,
            read=dict(
                count=self.read_count,
                rate=self.read_rate.serialize(),
                time=self.read_time
            ),
            write=dict(
                count=self.write_count,
                rate=self.write_rate.serialize(),
                time=self.write_time
            )
        )
