# -*- coding: utf-8 -*-
from raspysystem.raspycollection import RasPyCollection
from raspysystem.raspysamplelogger import RasPySampleLogger

class Sensor(object):
    TYPE_TEMP = "temp"
    TYPE_LIGHT = "light"
    TYPE_PRESSURE = "pressure"
    TYPE_HUMIDITY = "humidity"

    TYPES = (
        TYPE_TEMP,
        TYPE_LIGHT,
        TYPE_PRESSURE,
        TYPE_HUMIDITY
    )

    def serialize(self):
        return dict(
            value=self.serialize_value(),
            log=self.serialize_log()
        )

    def get_value(self):
        raise NotImplementedError

    def get_log(self):
        raise NotImplementedError

    def serialize_value(self):
        raise NotImplementedError

    def serialize_log(self):
        raise NotImplementedError

    def update(self, time):
        raise NotImplementedError

# class SensorCollection(RasPyCollection):

#     def __init__(self, collection):
#         RasPyCollection.__init__(self, collection)

#     def find_location(self, location):
#         return SensorCollection(filter(
#             lambda s: s.get_location() == location,
#             self._items
#         ))

#     def find_name(self, location, name):
#         return SensorCollection(filter(
#             lambda s: (
#                 s.get_location() == location and
#                 s.get_name() == name
#             ),
#             self._items
#         ))

#     def find_type(self, stype):
#         return SensorCollection(filter(
#             lambda s: s.get_type() == stype
#             , self._items
#         ))

#     def get(self, location, name, stype):
#         for s in self._items:
#             if s.equals(location, name, stype):
#                 return s
#         return None

class SensorFloatValue(Sensor):

    def __init__(self, maxlogs, windows):
        Sensor.__init__(self)
        self._log = RasPySampleLogger(maxlogs, windows)

    def get_value(self):
        return self._log.get_last_sample()

    def get_log(self):
        return self._log

    def serialize_value(self):
        return self.get_value()

    def serialize_log(self):
        return self._log.serialize()

    def update(self, time):
        value = self.update_value(time)
        self._log.log(time.jstimestamp(), value)

    def update_value(self, time):
        raise NotImplementedError

