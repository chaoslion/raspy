# -*- coding: utf-8 -*-
import os.path
from raspysystem.raspytask import RasPyTask
from socket import SocketControllerTask
from automat import AutomatControllerTask

class RCSocketTask(RasPyTask):

    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "rcsocket", True)

        self._subtasks = [
            SocketControllerTask(self),
            AutomatControllerTask(self)
        ]
