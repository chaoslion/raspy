# -*- coding: utf-8 -*-
import random
import math
from sensor import Sensor, SensorFloatValue

class SensorDS18B20(SensorFloatValue):
    W1PATH = "/sys/bus/w1/devices/"
    RETRIES = 3

    def __init__(self, w1address, maxlogs, windows):
        SensorFloatValue.__init__(self, maxlogs, windows)
        self._w1address = w1address

    def get_w1address(self):
        return self._w1address

    def _read_temp(self):
        path = self.W1PATH + self._w1address + "/w1_slave"

        with open(path) as file:
            w1result = file.read()

        w1result = w1result.splitlines()
        crc = w1result[0].split(" ")
        temp = w1result[1].split(" ")
        # example format
        # ['30', '00', '4b', '46', 'ff', 'ff', '0a', '10', '47', ':', 'crc=47', 'YES']
        # ['30', '00', '4b', '46', 'ff', 'ff', '0a', '10', '47', 't=24125']
        crc = crc[-1]
        if crc == "YES":
            temp = temp[-1][2:]
            return float(temp) / 1000.0
        return None

    def update_value(self, time):
        temp = None
        for retry in range(self.RETRIES):
            temp = self._read_temp()
            if not (temp is None):
                break
        return temp
