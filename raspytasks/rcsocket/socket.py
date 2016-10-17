# -*- coding: utf-8 -*-
import random
from raspysystem.raspycollection import RasPyCollection
from raspysystem.raspysamplelogger import RasPySampleLogger
from raspysystem.raspyenergymeter import RasPyEnergyMeter
from raspysystem.raspytask import RasPySimpleTask
from rcswitch import SwitchTypeB


class Socket(object):
    AUTOMAT_UNKNOWN = "?"
    # 2% noise
    NOISE_FULLSCALE = 0.02
    MODE_USER = 0
    MODE_AUTO = 1

    def __init__(
        self,
        location,
        name,
        prms,
        address,
        period,
        maxlogs,
        db_path,
        db_prefix
    ):

        self._automat = self.AUTOMAT_UNKNOWN
        self._automat_msg = self.AUTOMAT_UNKNOWN
        self._mode = self.MODE_USER

        self._name = name
        self._location = location
        self._address = address

        self._state_user = False
        self._state_auto = False

        self._last_state = False
        self._state_changed = False

        self._prms = prms
        self._meter = RasPyEnergyMeter(
            period,
            db_path,
            db_prefix
        )
        self._log = RasPySampleLogger(maxlogs)

    def get_mode(self):
        return self._mode

    def get_state_user(self):
        return self._state_user

    def get_state_auto(self):
        return self._state_auto

    def get_state_changed(self):
        return self._state_changed

    def get_name(self):
        return self._name

    def get_location(self):
        return self._location

    def get_address(self):
        return self._address

    def get_meter(self):
        return self._meter

    def switch_auto(self, state, automat, msg):
        self._automat = automat
        self._automat_msg = msg
        self._state_auto = state

    def mode_auto(self):
        self._mode = self.MODE_AUTO

    def mode_user(self, newstate):
        self._mode = self.MODE_USER
        self._state_user = newstate

    def get_state(self):
        if self._mode == self.MODE_AUTO:
            return self._state_auto
        return self._state_user

    def update(self, time):
        # change event generation
        self._state_changed = self.get_state() != self._last_state
        self._last_state = self.get_state()

        state = self.get_state()
        if state:
            noise = self._prms * self.NOISE_FULLSCALE
            power = self._prms + random.uniform(-noise, +noise)
        else:
            power = 0
        self._meter.update(time, power)
        self._log.log(time.jstimestamp(), 1 if state else 0)

    def serialize(self):
        return dict(
            name=self._name,
            location=self._location,
            state=self.get_state(),
            automat=self._automat,
            automat_msg=self._automat_msg,
            mode=self._mode,
            prms=self._prms,
            log=self._log.serialize(),
            energy=self._meter.serialize()
        )


class SocketCollection(RasPyCollection):

    def __init__(self, collection):
        RasPyCollection.__init__(self, collection)

    def find_name(self, name, invert=False):
        socks = filter(lambda s: (s.get_name() == name) ^ invert, self._items)
        return SocketCollection(socks)

    def find_location(self, location, invert=False):
        socks = filter(lambda s: (s.get_location() == location) ^ invert, self._items)
        return SocketCollection(socks)

    def get(self, address):
        for socket in self._items:
            if socket.get_address() == address:
                return socket
        return None

    def get_index(self, address):
        for index in range(len(self._items)):
            socket = self._items[index]
            if socket.get_address() == address:
                return index
        return -1

class SocketControllerTask(RasPySimpleTask):
    RF_TX_PIN = 4

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "socketctrl")

        self._rcswitch = SwitchTypeB(self.RF_TX_PIN, True)
        self._last_switch_count = 0
        self._sockets = list()
        # if user wants to switch all
        self._force_all = False

    def get_rcswitch(self):
        return self._rcswitch

    def get_sockets(self):
        return SocketCollection(self._sockets)

    # switch socket only if new state is not old state
    # so we dont spam rf every minute
    def _switch_all_sockets(self, time, force):
        for socket in self._sockets:

            if not force and not socket.get_state_changed():
                continue

            self._rcswitch.switch(
                time,
                socket.get_address(),
                socket.get_state()
            )
            self._last_switch_count += 1

    def _req_force_all(self, args, update):

        if not update:
            return self.req_statecheck(
                "force_all",
                self._force_all == True
            )

        self._force_all = True
        return self.REQ_PASS

    def _req_mode_user(self, args):
        address = args["address"]
        state = args["state"]
        index = self.get_sockets().get_index(address)

        if not update:
            if index < 0:
                self.loge("Socket was not found: {}".format(address))
                return self.REQ_FAIL
            return self.req_statecheck(
                "socket{}mode".format(index),
                (
                    socket.get_mode() == Socket.MODE_USER and
                    socket.get_state_user() == state
                )
            )

        socket.mode_user(state)
        return self.REQ_PASS

    def _req_mode_auto(self, args):
        address = args["address"]
        state = args["state"]
        index = self.get_sockets().get_index(address)

        if not update:
            if index < 0:
                self.loge("Socket was not found: {}".format(address))
                return self.REQ_FAIL
            return self.req_statecheck(
                "socket{}mode".format(index),
                    socket.get_mode() == Socket.MODE_AUTO
            )

        socket.mode_auto()
        return self.REQ_PASS

    def startup_event(self, db, cfg):
        maxlogs = self.kernel().get_updates24h()

        # 1) init switch
        self._rcswitch.hw_init()

        # 2) load from database
        # create tables if not exist
        db.execute(
            "CREATE TABLE IF NOT EXISTS '{}' ({}, {}, {}, {})".format(
            "rcsocket_sockets",
            "'address' TEXT PRIMARY KEY",
            "'location' TEXT",
            "'name' TEXT",
            "'prms' REAL"
            )
        )

        db.execute("SELECT * FROM rcsocket_sockets")
        for r in db.fetchall():
            loc = str(r["location"])
            name = str(r["name"])
            address = str(r["address"])

            # check address
            if self.get_sockets().get(address) is not None:
                self._logger.loge("Socket address is already taken: {}".format(name))
                return False

            if not self._rcswitch.is_valid_address(address):
                self.loge("Socket address is invalid: {}".format(address))
                return False

            socket = Socket(
                loc,
                name,
                float(r["prms"]),
                address,
                self.period(),
                maxlogs,
                self.kernel().get_databasepath(),
                "socket{}".format(len(self._sockets))
            )
            self._sockets.append(socket)

        # 3) register requests
        if not self.add_requests([
            ["force_all", dict()],
            ["mode_user", dict(address="string",state="bool")],
            ["mode_auto", dict(address="string")]
        ]):
            return False

        return True

    def run_event(self):
        time = self.time()

        # update state, energy and log
        for socket in self._sockets:
            socket.update(time)

        self._last_switch_count = 0
        self._force_all = False

        if time.new_hour():
            # force new state every hour
            self._switch_all_sockets(time, True)
        else:
            # switch sockets if needed
            self._switch_all_sockets(time, self._force_all)
        return True

    def report_event(self):
        return dict(
            sockets=[so.serialize() for so in self._sockets],
            switch=dict(
                count=self._rcswitch.get_txcount(),
                last_count=self._last_switch_count,
                code=self._rcswitch.get_txcode(),
                timestamp=self._rcswitch.get_txtimestamp()
            )
        )
