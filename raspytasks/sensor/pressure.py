# -*- coding: utf-8 -*-
import random
import math
from sensor import Sensor, SensorFloatValue

class SensorDummyPressure(SensorFloatValue):
    _PMIN = 990
    _PMAX = 1010

    def __init__(self, maxlogs, windows):
        SensorFloatValue.__init__(self, maxlogs, windows)

    def update_value(self, time):
        return random.uniform(self._PMIN, self._PMAX)
