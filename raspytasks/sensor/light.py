# -*- coding: utf-8 -*-
import math
from sensor import Sensor, SensorFloatValue

class SensorDummyLight(SensorFloatValue):
    FREQUENCY = 0.5

    def __init__(self, maxlogs, windows):
        SensorFloatValue.__init__(self, maxlogs, windows)
        self._norm_freq = self.FREQUENCY / maxlogs

    def update_value(self, time):
        minutes = 60 * time.hour + time.minute
        minutes /= 15
        level = 255.0 * math.sin(2.0 * math.pi * self._norm_freq * minutes)
        return round(level)
