# -*- coding: utf-8 -*-
from raspysamplelogger import RasPySampleLogger

class RasPyByteRate(object):
    def __init__(self, period, maxlog, windows=list()):

        self._period = period
        self._bytes_last = None
        self._ratelog = RasPySampleLogger(maxlog, windows)

    def calc(self, newbytes):
        # garbage measurment
        if newbytes is None:
            rate = None
        # suppress initial peak
        elif self._bytes_last is None:
            rate = 0
        # supress negative values, which happen on fritz reconnect
        elif newbytes < self._bytes_last:
            rate = None
        else:
            # get byte/s
            rate = float(newbytes - self._bytes_last) / self._period

        self._bytes_last = newbytes
        return rate

    def log(self, timestamp, newbytes):
        rate = self.calc(newbytes)
        self._ratelog.log(timestamp, rate)

    def serialize(self):
        return dict(
            total_bytes=self._bytes_last,
            rates=self._ratelog.serialize()
        )

class RasPyBitRate(RasPyByteRate):

    def calc(self, newbytes):
        rate = RasPyByteRate.calc(self, newbytes)
        # get bits/s
        if rate is not None:
            rate *= 8.0
        return rate
