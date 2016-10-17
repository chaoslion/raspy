# -*- coding: utf-8 -*-
import arrow
import simplejson as json
import requests
import ssl
from requests.auth import HTTPBasicAuth

from raspysystem.raspytask import RasPySimpleTask
from raspysystem.raspycollection import RasPyCollection
from raspysystem.raspysamplelogger import RasPySampleLogger


class WeatherData(object):

    def __init__(self, tf, wdata):
        self.time = tf.get(
            wdata.get("time", 0)
        )
        self.summary = wdata.get("summary")
        self.icon = wdata.get("icon")

        self.precipIntensity = wdata.get("precipIntensity")
        self.precipProbability = wdata.get("precipProbability")
        self.precipType = wdata.get("precipType")

        self.dewPoint = wdata.get("dewPoint")
        self.humidity = wdata.get("humidity")

        self.windSpeed = wdata.get("windSpeed")
        self.windBearing = wdata.get("windBearing")

        self.visibility = wdata.get("visibility")
        self.cloudCover = wdata.get("cloudCover")
        self.pressure = wdata.get("pressure")
        self.ozone = wdata.get("ozone")

    def serialize(self):
        return dict(
            time=self.time.jstimestamp(),
            summary=self.summary,
            icon=self.icon,
            precipIntensity=self.precipIntensity,
            precipProbability=self.precipProbability,
            precipType=self.precipType,
            dewPoint=self.dewPoint,
            humidity=self.humidity,
            windSpeed=self.windSpeed,
            windBearing=self.windBearing,
            visibility=self.visibility,
            cloudCover=self.cloudCover,
            pressure=self.pressure,
            ozone=self.ozone
        )


class WeatherDataHourly(WeatherData):

    def __init__(self, tf, wdata):
        WeatherData.__init__(self, tf, wdata)

        self.temperature = wdata.get("temperature")
        self.apparentTemperature = wdata.get("apparentTemperature")

    def serialize(self):
        data = WeatherData.serialize(self)
        data.update(dict(
            temperature=self.temperature,
            apparentTemperature=self.apparentTemperature
        ))
        return data

class WeatherDataDaily(WeatherData):

    def __init__(self, tf, wdata):
        WeatherData.__init__(self, tf, wdata)

        self.sunriseTime = tf.get(
            wdata.get("sunriseTime", 0)
        )
        self.sunsetTime = tf.get(
            wdata.get("sunsetTime", 0)
        )

        self.moonPhase = wdata.get("moonPhase")

        self.precipIntensityMax = wdata.get("precipIntensityMax")
        self.precipIntensityMaxTime = tf.get(
            wdata.get("precipIntensityMaxTime", 0)
        )

        self.temperatureMin = wdata.get("temperatureMin")
        self.temperatureMinTime = tf.get(
            wdata.get("temperatureMinTime", 0)
        )
        self.temperatureMax = wdata.get("temperatureMax")
        self.temperatureMaxTime = tf.get(
            wdata.get("temperatureMaxTime", 0)
        )

        self.apparentTemperatureMin = wdata.get("apparentTemperatureMin")
        self.apparentTemperatureMinTime = tf.get(
            wdata.get("apparentTemperatureMinTime", 0)
        )
        self.apparentTemperatureMax = wdata.get("apparentTemperatureMax")
        self.apparentTemperatureMaxTime = tf.get(
            wdata.get("apparentTemperatureMaxTime", 0)
        )


    def serialize(self):
        data = WeatherData.serialize(self)
        data.update(dict(
            sunriseTime=self.sunriseTime.jstimestamp(),
            sunsetTime=self.sunsetTime.jstimestamp(),
            moonPhase=self.moonPhase,
            precipIntensityMax=self.precipIntensityMax,
            precipIntensityMaxTime=self.precipIntensityMaxTime.jstimestamp(),
            temperatureMin=self.temperatureMin,
            temperatureMinTime=self.temperatureMinTime.jstimestamp(),
            temperatureMax=self.temperatureMax,
            temperatureMaxTime=self.temperatureMaxTime.jstimestamp(),
            apparentTemperatureMin=self.apparentTemperatureMin,
            apparentTemperatureMinTime=self.apparentTemperatureMinTime.jstimestamp(),
            apparentTemperatureMax=self.apparentTemperatureMax,
            apparentTemperatureMaxTime=self.apparentTemperatureMaxTime.jstimestamp()
        ))
        return data


class ReportHourly(object):
    def __init__(self, tf, wreport):
        self.summary = wreport.get("summary")
        self.icon = wreport.get("icon")
        self.data = [ WeatherDataHourly(tf, wd) for wd in wreport.get("data") ]

    def serialize(self):
        return dict(
            summary=self.summary,
            icon=self.icon,
            data=[ d.serialize() for d in self.data]
        )

class ReportDaily(object):
    def __init__(self, tf, wreport):
        self.summary = wreport.get("summary")
        self.icon = wreport.get("icon")
        self.data = [ WeatherDataDaily(tf, wd) for wd in wreport.get("data") ]

    def serialize(self):
        return dict(
            summary=self.summary,
            icon=self.icon,
            data=[ d.serialize() for d in self.data]
        )


class Alert(object):
    def __init__(self, tf, walert):
        self.title = walert.get("title")
        self.expires = tf.get(
            walert.get("expires", 0)
        )
        self.description = walert.get("description")
        self.uri = walert.get("uri")

    def serialize(self):
        return dict(
            title=self.title,
            expires=self.expires.jstimestamp(),
            description=self.description,
            uri=self.uri
        )

class ForecastIOTask(RasPySimpleTask):
    # _API_URL = "https://api.forecast.io/forecast"
    _API_URL = "https://api.darksky.net/forecast"

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "forecast")

        # log some values
        # we only store very 15min so maxlogs/15
        maxlogs = self.kernel().get_updates24h() / 15
        self._logtemp = RasPySampleLogger(maxlogs)
        self._logclouds = RasPySampleLogger(maxlogs)
        self._logpreci = RasPySampleLogger(maxlogs)


        self._updates = 0
        self._synctime = None
        self._currently = None
        self._hourly = None
        self._daily = None
        self._alerts = list()

        self._apikey = None
        self._timeout = None
        self._location = None

    def find_daily(self, day):

        if self._daily is not None:
            for w in self._daily.data:
                time = w.time.to('local')
                if time.day == day:
                    return w
        return None

    def valid(self):
        return self._updates > 0

    def get_updates(self):
        return self._updates

    def get_synctime(self):
        return self._synctime

    def get_currently(self):
        return self._currently

    def get_hourly(self):
        return self._hourly

    def get_daily(self):
        return self._daily

    def get_alerts(self):
        return self._alerts

    def _request_weather(self, time):
        try:
            r = requests.get(
                url="{}/{}/{},{}".format(
                    self._API_URL,
                    self._apikey,
                    self._location[0],
                    self._location[1]
                ),
                params=dict(
                    lang="de",
                    units="si"
                ),
                verify=True,
                timeout=self.kernel().get_timeout()
            )
        except requests.exceptions.RequestException as e:
            self.loge(e)
            return False

        if r.status_code != 200:
            self.loge("Status is not OK: {}".format(r.status_code))
            return False

        try:
            wdata = json.loads(r.content)
        except json.JSONDecodeError as e:
            self.loge("JSON is invalid: {}".format(e))
            return False

        # parse result
        self._updates += 1
        self._synctime = time.jstimestamp()

        tf = self.kernel().get_timefactory()

        self._currently = None
        if "currently" in wdata:
            self._currently = WeatherDataHourly(
                tf,
                wdata["currently"]
            )

        self._hourly = None
        if "hourly" in wdata:
            self._hourly = ReportHourly(
                tf,
                wdata["hourly"]
            )

        self._daily = None
        if "daily" in wdata:
            self._daily = ReportDaily(
                tf,
                wdata["daily"]
            )

        self._alerts = list()
        if "alerts" in wdata:
            for alert in wdata["alerts"]:
                self._alerts.append(
                    Alert(tf, alert)
                )

        return True

    def startup_event(self, db, cfg):
        if not self._config_expect(["location", "apikey"], cfg):
            return False
        self._apikey = cfg["apikey"]
        self._location = cfg["location"]
        return True

    def run_event(self):
        time = self.time()

        # every 15min
        if not time.every_quarter() and (self._updates!=0):
            return True

        jstime = time.jstimestamp()
        temp = None
        clouds = None
        preci = None

        if self._request_weather(time) and self._currently is not None:
            # could be None, but its ok
            preci = self._currently.precipProbability
            clouds = self._currently.cloudCover
            temp = self._currently.temperature

        # dont log first update
        if time.every_quarter():
            self._logtemp.log(jstime, temp)
            # convert to percent
            if not clouds is None:
                clouds = clouds * 100
            if not preci is None:
                preci = preci * 100
            self._logclouds.log(jstime, clouds)
            self._logpreci.log(jstime, preci)

        return True

    def report_event(self):
        return dict(
            logs=dict(
                temp=self._logtemp.serialize(),
                clouds=self._logclouds.serialize(),
                preci=self._logpreci.serialize()
            ),
            updates=self._updates,
            synctime=self._synctime,
            currently=None if self._currently is None else (
                self._currently.serialize()
            ),
            hourly=None if self._hourly is None else (
                self._hourly.serialize()
            ),
            daily=None if self._daily is None else (
                self._daily.serialize()
            ),
            alerts=[alert.serialize() for alert in self._alerts]
        )
