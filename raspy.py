# -*- coding: utf-8 -*-

if __name__ == "__main__":
    import os
    import sys
    import argparse

    path = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(path)

    # kernel
    from raspysystem.raspykernel import RasPyKernel
    # tasks
    from raspytasks.supply.task import SupplyTask
    from raspytasks.system.task import SystemTask
    from raspytasks.weather.task import WeatherTask
    from raspytasks.fritz.task import FritzTask
    from raspytasks.sensor.task import SensorTask
    from raspytasks.rcsocket.task import RCSocketTask
    from raspytasks.notifier.task import NotifierTask
    from raspytasks.traffic.task import TrafficTask
    # from raspytasks.stats.task import StatsTask

    parser = argparse.ArgumentParser(
        description="Smart periodic task execution application for the Raspberry Pi"
    )

    parser.add_argument("-d", "--debug", dest="debug", action="store_true", default=False)
    cfg = parser.parse_args()

    raspy = RasPyKernel(path, cfg.debug)

    # spawn tasks
    FritzTask(raspy)
    SystemTask(raspy)
    SupplyTask(raspy)
    RCSocketTask(raspy)
    TrafficTask(raspy)
    WeatherTask(raspy)
    SensorTask(raspy)
    NotifierTask(raspy)
    # StatsTask(raspy)

    raspy.run()
    raise Exception("self shutdown. see info log!")
