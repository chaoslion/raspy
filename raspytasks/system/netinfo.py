# -*- coding: utf-8 -*-
import psutil
from raspysystem.raspytask import RasPyTask, RasPySimpleTask
from raspysystem.raspydatarate import RasPyBitRate

class NetInfoTask(RasPySimpleTask):

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "net")

        maxlogs = self.kernel().get_updates24h()
        self.tx = RasPyBitRate(self.period(), maxlogs)
        self.rx = RasPyBitRate(self.period(), maxlogs)

    def run_event(self):
        timestamp = self.time().jstimestamp()

        ioc = psutil.net_io_counters()
        self.tx.log(timestamp, ioc.bytes_sent)
        self.rx.log(timestamp, ioc.bytes_recv)

        return True

    def report_event(self):
        return dict(
            tx=self.tx.serialize(),
            rx=self.rx.serialize()
        )
