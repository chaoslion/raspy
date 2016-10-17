# -*- coding: utf-8 -*-
import wiringpi2
import os.path

from raspysystem.raspylogger import RasPyLogger
from raspysystem.raspytask import RasPySimpleTask

import raspytasks.fritz.landevice
import raspytasks.sensor.sensor

class Automat(RasPyLogger):

    def __init__(self, ctx, priority):
        RasPyLogger.__init__(
            self,
            ctx["parent"],
            ctx["name"]
        )

        self._priority = priority
        self._name = ctx["name"]

        # add shortcuts
        for key, dst in ctx["shortcuts"].iteritems():
            setattr(self, key, dst)

        # add workers
        # for key, worker in ctx["workers"].iteritems():
        #     setattr(self, key, worker)

    def run(self, time):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def get_priority(self):
        return self._priority

    def on(self, socket, message):
        socket.switch_auto(True, self._name, message)

    def off(self, socket, message):
        socket.switch_auto(False, self._name, message)

class AutomatControllerTask(RasPySimpleTask):

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "automatctrl")
        self._automats = list()
        self._scriptenv = None

    def _find_automat(self, name):
        for automat in self._automats:
            if automat["name"] == name:
                return automat
        return None

    def _start_all_automats(self):
        for automat in self._automats:
            if not self._start_automat(automat):
                return False

        # sort and run automats
        # high priority(0) must come last
        # so reverse == true
        self._automats.sort(
            key=lambda automat: automat["priority"],
            reverse=True
        )
        return True

    def _stop_all_automats(self):
        for automat in self._automats:
            self._stop_automat(automat)

    def _start_automat(self, automat):
        name = automat["name"]
        if automat["instance"] is not None:
            self.loge("Can not restart Automat: {}".format(name))
            return False

        # load automat script
        filename = automat["filename"]

        try:
            with open(filename, 'r') as f:
                code = f.read()
        except EnvironmentError as e:
            self.loge("Failed to load Automat script: {}".format(e))
            return False

        try:
            compiled_code = compile(code, filename, 'exec')
        except SyntaxError as e:
            self.loge("Syntax error in Automat {}: {}".format(name, e))
            return False


        try:
            slocals = dict()
            exec(compiled_code, self._scriptenv["globals"], slocals)

            # start instance
            automat["instance"] = slocals["Automat"](
                dict(
                    parent=self,
                    name=name,
                    # workers=self._scriptenv["workers"],
                    shortcuts=self._scriptenv["shortcuts"]
                )
            )

            automat["priority"] = automat["instance"].get_priority()
        except Exception as e:
            self.loge("Error in Automat: {}".format(name))
            self.loge(e)
            return False

        self.logd("Start Automat: {}".format(name))
        automat["instance"].start()
        return True


    def _stop_automat(self, automat):
        if automat["instance"] is None:
            return
        self.logd("Stop Automat: {}".format(automat["name"]))
        automat["instance"].stop()
        automat["instance"] = None

    # def _req_start(self, arg):
    #     name = arg["name"]
    #     automat = self._find_automat(name)
    #     if automat is None:
    #         self.loge("automat was not found: {}".format(name))
    #         return self.REQ_FAIL

    #     self._start_automat(automat)

    #     return self.REQ_PASS

    # def _req_stop(self, arg):
    #     name = arg["name"]
    #     automat = self._find_automat(name)
    #     if automat is None:
    #         self.loge("automat was not found: {}".format(name))
    #         return self.REQ_FAIL

    #     self._stop_automat(automat)

    #     return self.REQ_PASS

    # def _req_restart(self, arg):
    #     name = arg["name"]
    #     automat = self._find_automat(name)
    #     if automat is None:
    #         self.loge("automat was not found: {}".format(name))
    #         return self.REQ_FAIL

    #     self._stop_automat(automat)
    #     self._start_automat(automat)

    #     return self.REQ_PASS

    def get_active(self):
        count = 0
        for automat in self._automats:
            if automat["instance"] is not None:
                count += 1
        return count

    def startup_event(self, db, cfg):

        # 1) load automat scripts
        pcpath = self.kernel().get_path()

        # its ok if no items are provided
        automats = cfg.get("items")
        if automats is None:
            self.logd("No Automats found")
            return True

        for name in automats:

            # check if name is unique
            if self._find_automat(name) is not None:
                self.loge("Automat name is not unique: {}".format(name))
                return False

            filename = os.path.join(
                pcpath,
                "automats",
                "{}.py".format(name)
            )

            # check if script exists
            if not os.path.exists(filename):
                self.loge("Automat script was not found: {}".format(filename))
                return False

            automat = dict(
                instance=None,
                name=name,
                priority=0,
                filename=filename
            )
            self._automats.append(automat)


        # 2) setup environment
        self._scriptenv = dict(
            shortcuts=dict(
                sockets=self.kernel().find_task("rcsocket")["socketctrl"].get_sockets(),
                devices=self.kernel().find_task("fritz")["landevicectrl"].get_devices(),
                sensors=self.kernel().find_task("sensor").get_sensors(),
                weather=self.kernel().find_task("weather")
            ),
            globals=dict(
                # mandatory
                SocketAutomat=Automat,
                # tasks classes
                LanDevice=raspytasks.fritz.landevice.LanDevice,
                Sensor=raspytasks.sensor.sensor.Sensor
            )
        )

        # 3) start all automats
        if not self._start_all_automats():
            return False

        # 4) register requests
        # if not self.add_requests([
        #     ["start", dict(name="string")],
        #     ["stop", dict(name="string")],
        #     ["restart", dict(name="string")]
        # ]):
        #     return False

        return True

    def run_event(self):
        time = self.time()
        for automat in self._automats:
            instance = automat["instance"]
            if instance is None:
                continue
            self.logd("Run: {}".format(automat["name"]))
            automat["instance"].run(time)

        return True

    def report_event(self):
        return dict(
            active=self.get_active(),
            count=len(self._automats)
        )
