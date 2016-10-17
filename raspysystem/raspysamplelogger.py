# -*- coding: utf-8 -*-
from math import fsum
from collections import deque

class RasPyRange(object):
    def __init__(self):
        self._min = None
        self._max = None

    def set_values(self, minval, maxval):
        self._min = minval
        self._max = maxval

    def clear(self):
        self._min = None
        self._max = None

    def get_min(self):
        return self._min

    def get_max(self):
        return self._max

# multi window moving average
class RasPyMovingAverager(object):

    # windows:
    # ascending order
    # no duplicates
    # maxlen => max(windows)
    def __init__(self, windows):
        self._samples_list = list()
        self._samples = deque(maxlen=windows[-1])
        self._averages = [None for _ in windows]
        self._ranges = [RasPyRange() for _ in windows]
        self._windows = windows

    def get_averages(self):
        return self._averages

    def get_ranges(self):
        return self._ranges

    def get_windows(self):
        return self._windows

    def clear(self):
        del self._samples_list[:]
        self._samples.clear()
        for i in range(len(self._windows)):
            self._averages[i] = None
            self._ranges[i].clear()

    # samples is array of windows
    def calc_average(self, vsample_list):
        for i in range(len(self._windows)):
            vsamples = vsample_list[i]
            average = None
            if len(vsamples) > 0:
                average = fsum(vsamples) / len(vsamples)
            self._averages[i] = average

    # samples is array of windows
    def calc_range(self, vsample_list):
        for i in range(len(self._windows)):
            vsamples = vsample_list[i]
            minval = None
            maxval = None
            if len(vsamples) > 0:
                minval = min(vsamples)
                maxval = max(vsamples)
            self._ranges[i].set_values(minval, maxval)

    def postprocess_valid_samples(self, valid_samples_list):
        self.calc_average(valid_samples_list)
        self.calc_range(valid_samples_list)

    def append(self, sample):
        # append sample
        self._samples.append(sample)
        # update samples list
        self._samples_list = [x for x in self._samples]
        valid_samples = [
            [
                # get window[x] items
                # starting from latest(==back of array)
                x for x in self._samples_list[-win:] if x is not None
            ] for win in self._windows
        ]
        self.postprocess_valid_samples(valid_samples)

    def serialize(self):
        return dict(
            windows=self._windows,
            averages=self._averages,
            ranges=[
                [
                    r.get_min(),
                    r.get_max()
                ] for r in self._ranges
            ]
        )

# multi window averager with timestamps
class RasPySampleLogger(RasPyMovingAverager):

    # ->WINDOWS MUST BE IN ACCENDING ORDER!
    # ->BIGGEST ELEMENT IN WINDOWS !== MAXLOG!
    def __init__(self, maxlog, windows=list()):
        RasPyMovingAverager.__init__(self, windows + [maxlog])
        self._avgsamples = deque(maxlen=maxlog)
        # track timestamps for min/max time
        self._timestamps = deque(maxlen=maxlog)
        # min/max time of the biggest array
        self._mintime = None
        self._maxtime = None

    def get_last_sample(self):
        if len(self._samples) > 0:
            return self._samples[-1]
        return None

    def get_start_time(self):
        if len(self._timestamps) > 0:
            return self._timestamps[0]
        return None

    def get_last_average(self):
        if len(self._avgsamples) > 0:
            return self._avgsamples[-1]
        return None

    # overload
    def clear(self):
        RasPyMovingAverager.clear(self)
        self._avgsamples.clear()
        self._timestamps.clear()
        self._starttime = None
        self._mintime = None
        self._maxtime = None

    def postprocess_valid_samples(self, valid_samples_list):
        RasPyMovingAverager.postprocess_valid_samples(
            self,
            valid_samples_list
        )
        # update min/max timestamps
        # find index of min, max of total sample array
        self._mintime = None
        self._maxtime = None
        if len(valid_samples_list[-1]) > 0:
            self._mintime = self._timestamps[
                valid_samples_list[-1].index(
                    self._ranges[-1].get_min()
                )
            ]
            self._maxtime = self._timestamps[
                valid_samples_list[-1].index(
                    self._ranges[-1].get_max()
                )
            ]

    # add separated log to recalculate start time
    def log(self, timestamp, sample):
        self._timestamps.append(timestamp)
        self.append(sample)
        self._avgsamples.append(self._averages[-1])

    # overload
    def serialize(self):
        output = RasPyMovingAverager.serialize(self)
        output.update(dict(
            samples=self._samples_list,
            avgsamples=[x for x in self._avgsamples],
            starttime=self.get_start_time(),
            mintime=self._mintime,
            maxtime=self._maxtime,
            last=self.get_last_sample()
        ))
        return output
