# -*- coding: utf-8 -*-
import os
import psutil
from raspysystem.raspytask import RasPyTask, RasPySimpleTask
from raspysystem.raspydatarate import RasPyBitRate

class ProcessInfoTask(RasPySimpleTask):

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "process")

        self._process = None
        self.rss = 0
        self.cpu_usage = 0
        self.read_count = 0
        self.write_count = 0
        self.read_bytes = 0
        self.write_bytes = 0

    def startup_event(self, db, cfg):
        pid = os.getpid()
        self._process = psutil.Process(pid)
        return True

    def run_event(self):
        self.rss = self._process.memory_info().rss
        self.cpu_usage = self._process.cpu_percent()

        io = self._process.io_counters()
        self.read_count = io.read_count
        self.write_count = io.write_count
        self.read_bytes = io.read_bytes
        self.write_bytes = io.write_bytes
        return True

    def report_event(self):
        return dict(
            rss=self.rss,
            cpu_usage=self.cpu_usage,
            read=dict(
                count=self.read_count,
                bytes=self.read_bytes
            ),
            write=dict(
                count=self.write_count,
                bytes=self.write_bytes
            )
        )
