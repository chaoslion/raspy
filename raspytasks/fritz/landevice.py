# -*- coding: utf-8 -*-
from raspysystem.raspycollection import RasPyCollection
from raspysystem.raspysamplelogger import RasPySampleLogger
from raspysystem.raspytask import RasPySimpleTask
from fritzbox import FritzboxReaderError

class LanDevice(object):
    TYPE_MOBILE = 0x01
    TYPE_TABLET = 0x02
    TYPE_LAPTOP = 0x04
    TYPE_DESKTOP = 0x08

    TYPES = (
        TYPE_MOBILE,
        TYPE_TABLET,
        TYPE_LAPTOP,
        TYPE_DESKTOP
    )

    def __init__(self, owner, mac, dtype, maxlogs):
        self._mac = mac
        self._owner = owner
        self._type = dtype
        self._state = None
        self._last_state = None
        self._statelog = RasPySampleLogger(maxlogs)

        self._interface = unicode()
        self._hostname = unicode()
        self._ip4 = unicode()
        self._leasetime = 0

        self._toff = 0
        self._ton = 0


    def get_mac(self):
        return self._mac

    def get_owner(self):
        return self._owner

    def get_type(self):
        return self._type

    def get_state(self):
        return self._state

    def get_ton(self):
        return self._ton

    def get_toff(self):
        return self._toff

    def update(self, timestamp, new_state):

        # update state
        self._last_state = self._state
        self._state = new_state


        # do not count, if state is undefined
        # keep old counters
        if new_state is not None:
            # update online/offline counters
            if self.went_off():
                self._toff = 0
            elif self.went_on():
                self._ton = 0
            elif self.online():
                self._ton += 1
            else:
                self._toff += 1



        self._statelog.log(timestamp, (
            None if new_state is None else (
                1 if new_state else 0)
            )
        )

    def update_info(self, interface, hostname, ip4, leasetime):
        # update info
        self._interface = interface
        self._hostname = hostname
        self._ip4 = ip4
        self._leasetime = leasetime

    def serialize(self):
        return dict(
            owner=self._owner,
            type=self._type,
            state=self._state,
            log=self._statelog.serialize(),
            mac=self._mac,
            interface=self._interface,
            hostname=self._hostname,
            leasetime=self._leasetime,
            ip=self._ip4,
            ton=self._ton,
            toff=self._toff
        )

    def online(self):
        return self._state == True

    def offline(self):
        return self._state == False

    def undefined(self):
        return self._state is None

    def went_on(self):
        return self._last_state == False and self._state == True

    def went_off(self):
        return self._last_state == True and self._state == False

    def online_since(self, threshold):
        return self.online() and self._ton >= threshold

    def offline_since(self, threshold):
        return self.offline() and self._toff >= threshold

    def went_on_after(self, threshold):
        return self.went_on() and self._toff >= threshold

    def went_off_after(self, threshold):
        return self.went_off() and self._ton >= threshold

class LanDeviceCollection(RasPyCollection):

    def __init__(self, collection):
        RasPyCollection.__init__(self, collection)

    def find_type(self, dtype, invert=False):
        devs = filter(lambda dev: ((dev.get_type() & dtype) > 0) ^ invert, self._items)
        return LanDeviceCollection(devs)

    def find_owner(self, owner, invert=False):
        devs = filter(lambda dev: (dev.get_owner() == owner) ^ invert, self._items)
        return LanDeviceCollection(devs)

    def get(self, mac):
        for dev in self._items:
            if dev.get_mac() == mac:
                return dev
        return None

    def find_others(self, device):
        devs = list()
        for dev in self._items:
            if dev in devices:
                continue
            devs.append(dev)
        return LanDeviceCollection(devs)

    def online(self):
        return LanDeviceCollection(filter(lambda dev: dev.online(), self._items))

    def offline(self):
        return LanDeviceCollection(filter(lambda dev: dev.offline(), self._items))

    def went_on(self):
        return LanDeviceCollection(filter(lambda dev: dev.went_on(), self._items))

    def went_off(self):
        return LanDeviceCollection(filter(lambda dev: dev.went_off(), self._items))

    def online_since(self, threshold):
        return LanDeviceCollection(filter(lambda dev: dev.online_since(threshold), self._items))

    def offline_since(self, threshold):
        return LanDeviceCollection(filter(lambda dev: dev.offline_since(threshold), self._items))

    def went_on_after(self, threshold):
        return LanDeviceCollection(filter(lambda dev: dev.went_on_after(threshold), self._items))

    def went_off_after(self, threshold):
        return LanDeviceCollection(filter(lambda dev: dev.went_off_after(threshold), self._items))

    def all_are_online(self):
        return len(self.offline()) == 0

    def all_are_offline(self):
        return len(self.online()) == 0

    def oom_went_on(self):
        return len(self.went_on()) > 0

    def oom_went_off(self):
        return len(self.went_off()) > 0

    def oom_went_on_after(self, threshold):
        return len(self.went_on_after(threshold)) > 0

    def oom_went_off_after(self, threshold):
        return len(self.went_off_after(threshold)) > 0

class LanDeviceControllerTask(RasPySimpleTask):

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "landevicectrl")
        self._devices = list()
        self._reader = None
        # self._nmap = nmap.PortScanner()

    def set_reader(self, reader):
        self._reader = reader

    def get_devices(self):
        return LanDeviceCollection(self._devices)

    def startup_event(self, db, cfg):
        maxlogs = self.kernel().get_updates24h()

        # create tables if not exist
        db.execute(
            "CREATE TABLE IF NOT EXISTS '{}' ({}, {}, {})".format(
            "fritz_devices",
            "'mac' TEXT PRIMARY KEY",
            "'owner' TEXT",
            "'type' INTEGER"
            )
        )
        db.execute("SELECT * FROM fritz_devices")
        for r in db.fetchall():
            mac = str(r["mac"])
            devtype = int(r["type"])
            use = int(r["use"])

            if use == 0:
                continue

            if self.get_devices().get(mac) is not None:
                self._logger.loge("Device is already registered: {}".format(mac))
                return False

            if not (devtype in LanDevice.TYPES):
                self._logger.loge("Device Type is invalid: {}".format(devtype))
                return False


            dev = LanDevice(
                str(r["owner"]),
                mac,
                devtype,
                maxlogs
            )
            self._devices.append(dev)
        return True

    def report_event(self):
        return dict(
            devices=[dev.serialize() for dev in self._devices]
        )

    def run_event(self):
        timestamp = self.time().jstimestamp()

        for dev in self._devices:

            try:
                r = self._reader.hosts_get_specific_host_entry(dev.get_mac())
                dev.update(timestamp, int(r["NewActive"]) == 1)
                dev.update_info(
                    r["NewInterfaceType"],
                    r["NewHostName"],
                    r["NewIPAddress"],
                    int(r["NewLeaseTimeRemaining"])
                )
            except FritzboxReaderError as e:
                self.loge("Failed get get host {} because {}".format(dev.get_mac(), e))
                # assume not active on fritzbox error
                dev.update(timestamp, None)

        return True
