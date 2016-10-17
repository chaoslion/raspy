# -*- coding: utf-8 -*-
from raspysystem.raspytask import RasPyTask
from forecastio import ForecastIOTask
from cam import CameraTask


class WeatherTask(RasPyTask):


    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "weather")

        self._subtasks = [
            ForecastIOTask(self),
            CameraTask(self)
        ]


