# -*- coding: utf-8 -*-
import math

class StatsReport(object):

    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def serialize(self):
        return dict(
            name=self._name
        )

    def update(self, arg):
        raise NotImplementedError()

    def reset(self):
        raise NotImplementedError()


class StatsMean(StatsReport):

    def __init__(self, name):
        StatsReport.__init__(self, name)

        self._acc = 0
        self._mean = 0
        self._stddiv = 0
        self._max = 0
        self._min = 0

    def get_acc(self):
        return self._acc

    def get_mean(self):
        return self._mean

    def get_stddiv(self):
        return self._stddiv

    def get_max(self):
        return self._max

    def get_min(self):
        return self._min

    def reset(self):
        self._acc = 0
        self._mean = 0
        self._stddiv = 0
        self._max = 0
        self._min = 0


    # arg is list
    def update(self, arg):
        size = len(arg)
        last = arg[size-1]

        self._acc += last
        self._mean = self._acc / size


        var = [math.pow(s - self._mean, 2) for s in arg]
        var = math.fsum(var)
        self._stddiv = math.sqrt(var)

        self._max = max(self._max, last)
        self._min = min(self._min, last)

    def serialize(self):
        output = StatsReport.serialize(self)
        output.update(dict(
            mean=self._mean,
            stddiv=self._stddiv,
            max=self._max,
            min=self._min
        ))


class StatsCount(object):
    def __init__(self, name):
        self._name = name
        self._limit = None
        self._cnt = 0

    def set_limit(self, limit):
        self._limit = limit

    def get_cnt(self):
        return self._cnt

    def reset(self):
        self._cnt = 0

    def update(self, arg):
        self._cnt += arg
        if self._limit is None:
            return
        if self._cnt >= self._limit:
            self._cnt = self._limit

    def serialize(self):
        output = StatsReport.serialize(self)
        output.update(dict(
            cnt=self._cnt
        ))

