# -*- coding: utf-8 -*-
from raspysystem.raspytask import RasPyTask
from sensor import Sensor
from temp import SensorDS18B20
from light import SensorDummyLight
from humidity import SensorDummyHumidity
from pressure import SensorDummyPressure





class SensorTask(RasPyTask):

    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "sensor")

        self._maxlogs = self.kernel().get_updates24h() / 15
        self._sensors = dict()
        self._drivers = dict()

    # drivers
    def _temp_ds18b20(self, driverinfo):
        return SensorDS18B20(driverinfo, self._maxlogs, list())

    def _light_dummy(self, driverinfo):
        return SensorDummyLight(self._maxlogs, list())

    def _humidity_dummy(self, driverinfo):
        return SensorDummyPressure(self._maxlogs, list())

    def _pressure_dummy(self, driverinfo):
        return SensorDummyHumidity(self._maxlogs, list())
    # drivers end

    def get_sensors(self):
        return self._sensors

    def startup_event(self, db, cfg):
        # register device drivers
        # every type must be registed even if dict is empty!
        self._drivers[Sensor.TYPE_TEMP] = dict(
            ds18b20=self._temp_ds18b20
        )
        self._drivers[Sensor.TYPE_LIGHT] = dict(
            dummy=self._light_dummy
        )
        self._drivers[Sensor.TYPE_HUMIDITY] = dict(
            dummy=self._humidity_dummy
        )
        self._drivers[Sensor.TYPE_PRESSURE] = dict(
            dummy=self._pressure_dummy
        )

        # create tables if not exist
        db.execute(
            "CREATE TABLE IF NOT EXISTS {} ({}, {}, {}, {}, {}, {})".format(
                "'sensor_sensors'",
                "'id' INTEGER PRIMARY KEY",
                "'type' TEXT",
                "'location' TEXT",
                "'name' TEXT",
                "'driver' TEXT",
                "'driverinfo' TEXT"
            )
        )

        db.execute("SELECT * FROM sensor_sensors")
        for r in db.fetchall():
            stype = str(r["type"])
            slocation = str(r["location"])
            sname = str(r["name"])
            sdriver = str(r["driver"])
            sdriverinfo = str(r["driverinfo"])

            # check type and drivers
            if not (stype in Sensor.TYPES):
                self.loge("Sensor has invalid type: {}".format(stype))
                return False

            if sdriver in self._drivers[stype]:
                # type and driver match

                # new sensor type?
                if not stype in self._sensors:
                    self._sensors[stype] = dict()

                # new location?
                if not slocation in self._sensors[stype]:
                    self._sensors[stype][slocation] = dict()

                if sname in self._sensors[stype][slocation]:
                    self._logger.loge("Sensor is not unique: {}->{}({})".format(
                        slocation,
                        sname,
                        stype
                    ))
                    return False

                self._sensors[stype][slocation][sname] = (
                    self._drivers[stype][sdriver](sdriverinfo)
                )
            else:
                self.loge("Unsupported driver: {}".format(sdriver))
                return False

        return True

    def run_event(self):
        time = self.time()

        # every 15min
        if not time.every_quarter():
            return True

        for stype in self._sensors:
            for sloc in self._sensors[stype]:
                for sname in self._sensors[stype][sloc]:
                    self._sensors[stype][sloc][sname].update(time)
        return True

    def report_event(self):
        output = dict()
        for stype in self._sensors:
            output[stype] = dict()
            output[stype]["locations"] = list()
            for slocation in self._sensors[stype]:
                locitems = list()
                for sname in self._sensors[stype][slocation]:
                    locitems.append(dict(
                        name=sname,
                        sensor=self._sensors[stype][slocation][sname].serialize()
                    ))
                output[stype]["locations"].append(
                    dict(name=slocation, items=locitems)
                )
        return output
