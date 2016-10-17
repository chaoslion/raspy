# -*- coding: utf-8 -*-
from raspysystem.raspytask import RasPyTask
from diskinfo import DiskInfoTask
from memoryinfo import MemoryInfoTask
from netinfo import NetInfoTask
from processinfo import ProcessInfoTask
from osinfo import OSInfoTask
from tempcontrol import TempControlTask

class SystemTask(RasPyTask):

    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "system")

        windows = [5, 15, 60]

        self._subtasks = [
            DiskInfoTask(self),
            NetInfoTask(self),
            MemoryInfoTask(self),
            ProcessInfoTask(self),
            OSInfoTask(self, windows),
            TempControlTask(self, windows)
        ]
