# -*- coding: utf-8 -*-
import psutil
from raspysystem.raspytask import RasPyTask, RasPySimpleTask
from raspysystem.raspydatarate import RasPyByteRate

class MemoryInfoTask(RasPySimpleTask):

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "memory")

        self.mem_total = 0
        self.mem_used = 0
        self.mem_available = 0
        self.mem_free = 0
        self.mem_buffers = 0
        self.mem_cached = 0

        self.swap_total = 0
        self.swap_used = 0
        self.swap_free = 0

    def run_event(self):
        mem = psutil.virtual_memory()
        self.mem_total = mem.total
        self.mem_available = mem.available
        self.mem_used = mem.used
        self.mem_free = mem.free
        self.mem_buffers = mem.buffers
        self.mem_cached = mem.cached

        swap = psutil.swap_memory()
        self.swap_total = swap.total
        self.swap_used = swap.used
        self.swap_free = swap.free
        return True


    def report_event(self):
        return dict(
            vmem=dict(
                total=self.mem_total,
                used=self.mem_used,
                available=self.mem_available,
                free=self.mem_free,
                buffers=self.mem_buffers,
                cached=self.mem_cached
            ),
            swap=dict(
                total=self.swap_total,
                used=self.swap_used,
                free=self.swap_free
            )
        )
