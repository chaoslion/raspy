# -*- coding: utf-8 -*-
from raspysystem.raspytask import RasPyTask
from raspysystem.raspydatarate import RasPyBitRate

import fritzbox
from landevice import LanDeviceControllerTask



class FritzTask(RasPyTask):

    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "fritz")

        self._fbreader = None
        self._uptime = 0
        self._dsl_uptime = 0
        self._fritz_time = None
        self._upgrade = False
        self._modelname = unicode()
        self._software = unicode()


        maxlogs = self.kernel().get_updates24h()
        windows = [5, 15, 60]
        self._tx = RasPyBitRate(self.period(), maxlogs, windows)
        self._rx = RasPyBitRate(self.period(), maxlogs, windows)

        self._txrate_max = 0
        self._rxrate_max = 0
        self._txrate_limit = 0
        self._rxrate_limit = 0
        self._subtasks = [
            LanDeviceControllerTask(self)
        ]

    def get_fbreader(self):
        return self._fbreader

    def _update_traffic(self):
        time = self.time()

        try:
            rrx = self._fbreader.wanif_get_total_bytes_received()
            rx_bytes = int(rrx["NewTotalBytesReceived"])
        except fritzbox.FritzboxReaderError as e:
            self.loge("Failed to get rx bytes: {}".format(e))
            rx_bytes = None

        try:
            rtx = self._fbreader.wanif_get_total_bytes_sent()
            tx_bytes = int(rtx["NewTotalBytesSent"])
        except fritzbox.FritzboxReaderError as e:
            self.loge("Failed to get tx bytes: {}".format(e))
            tx_bytes = None

        self._rx.log(time.jstimestamp(), rx_bytes)
        self._tx.log(time.jstimestamp(), tx_bytes)

        try:
            r = self._fbreader.wandslif_get_info()
            self._txrate_max = int(r["NewUpstreamCurrRate"])
            self._txrate_limit = int(r["NewUpstreamMaxRate"])
            self._rxrate_max = int(r["NewDownstreamCurrRate"])
            self._rxrate_limit = int(r["NewDownstreamMaxRate"])
        except fritzbox.FritzboxReaderError as e:
            self.loge("Failed to get dsl info: {}".format(e))

    # disconnection safe
    def run_event(self):
        # the following calls always return valid data
        # if there is a network connection
        try:
            r = self._fbreader.devinfo_get_info()
            self._uptime =  int(r["NewUpTime"])
            self._modelname = r["NewModelName"]
            self._software = r["NewSoftwareVersion"]
        except fritzbox.FritzboxReaderError as e:
            self.loge("Failed to get device info: {}".format(e))

        try:
            r = self._fbreader.userif_get_info()
            self._upgrade = int(r["NewUpgradeAvailable"]) == 1
        except fritzbox.FritzboxReaderError as e:
            self.loge("Failed to get upgrade info: {}".format(e))

        try:
            r = self._fbreader.time_get_info()
            local_time = r["NewCurrentLocalTime"]
            # time in DateTime: convert to timestamp
            # 2015-08-11T10:55:05+02:00
            local_time = self.kernel().get_timefactory().get(local_time)
            self._fritz_time = local_time.timestamp
        except fritzbox.FritzboxReaderError as e:
            self.loge("Failed to get localtime info: {}".format(e))

        # WAN UPTIME, dont care for now
        # try:
        #     r = self._fbreader.wanip_get_status_info()
        #     self.dsl_uptime = int(r["NewUptime"])
        # except fritzbox.FritzboxReaderError as e:
        #     self.loge("failed to get localtime info: {}".format(e))


        # traffic information is reset after reconnect
        self._update_traffic()
        return True

    def report_event(self):
        return dict(
            router=dict(
                model=self._modelname,
                software=self._software,
                uptime=self._uptime,
                upgrade=self._upgrade,
                localtime=self._fritz_time
            ),
            dsl=dict(
                # uptime=self._dsl_uptime,
                tx=dict(
                    rate=self._tx.serialize(),
                    ratemax=self._txrate_max,
                    ratelimit=self._txrate_limit,
                ),
                rx=dict(
                    rate=self._rx.serialize(),
                    ratemax=self._rxrate_max,
                    ratelimit=self._rxrate_limit
                )
            )
        )

    def startup_event(self, db, cfg):
        self._fbreader = fritzbox.FritzboxReader(
            cfg.get("user", "user"),
            cfg.get("password", ""),
            2.0,
            cfg.get("ip" ,"fritz.box")
        )

        self["landevicectrl"].set_reader(self._fbreader)
        return True
