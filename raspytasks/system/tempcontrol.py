# -*- coding: utf-8 -*-
import os
import psutil
import wiringpi2
import time
from math import fsum
from raspysystem.raspytask import RasPySimpleTask
from raspysystem.raspysamplelogger import RasPySampleLogger


class PIDController(object):

    def __init__(self, sample_time, inverse=False):
        self._kp = 0
        self._ki = 0
        self._kd = 0

        self._inverse = inverse
        self._sample_time = sample_time

        self._esum = 0
        self._dinput = 0
        self._last_input = 0

        self._ref = 0
        self._outmin = 0
        self._outmax = 0


    def get_output_max(self):
        return self._outmax

    def get_output_min(self):
        return self._outmin

    def reset(self):
        self._esum = 0
        self._dinput = 0
        self._last_input = 0

    def set_coeff(self, kp, ki, kd):
        self._kp = kp
        self._ki = ki * self._sample_time
        self._kd = kd / self._sample_time

        if self._inverse:
            self._kp = -self._kp
            self._ki = -self._ki
            self._kd = -self._kd

        self.reset()

    def set_limit(self, outmin, outmax):
        self._outmin = outmin
        self._outmax = outmax
        self.reset()

    def set_ref(self, ref):
        self._ref = float(ref)
        self.reset()

    def get_ref(self):
        return self._ref

    def compute(self, value):

        e = self._ref - value

        self._esum += self._ki * e
        if self._esum > self._outmax:
            self._esum = self._outmax
        elif self._esum < self._outmin:
            self._esum = self._outmin

        self._dinput = value - self._last_input
        self._last_input = value

        output = (
            self._kp * e +
            self._esum -
            self._kd * self._dinput
        )

        if output > self._outmax:
            output = self._outmax
        elif output < self._outmin:
            output = self._outmin

        return output

class TempControlTask(RasPySimpleTask):
    PROFILES = [25, 30, 35, 40, 45, 50, 55, 60]
    PWM_PIN = 23
    PID_P = 1.0
    PID_I = 0.05
    PID_D = 0.25

    # 19.2e6/DIV/RANGE = 18.750kHz pwm freq
    PWM_CLK_DIV = 2
    PWM_RANGE = 256

    # fan off threshold, in C
    ECO_THRESHOLD = 5
    # in s
    FAN_SPINUP = 2500
    # fan current cutoff threshold, 50%
    FAN_THRESHOLD = 0.5
    # recalibration pwm step
    FAN_RECAL_PWM = 15
    # if pwm=pwm_dead -> fan is dead :(
    FAN_DEAD_PWM = 230

    def __init__(self, parent, windows):
        RasPySimpleTask.__init__(self, parent, "tempctrl")

        self._pid = PIDController(
            self.period(),
            True
        )

        maxlogs = self.kernel().get_updates24h()
        self._templog = RasPySampleLogger(maxlogs, windows)
        self._speedlog = RasPySampleLogger(maxlogs, windows)

        self._minspeed = 0
        self._minpwm = 0
        self._pwm = 0
        self._idleload = 0
        self._maxload = 0
        self._caltime = 0

        # eco mode = fan off, if temp < profile - ECO_THRESHOLD
        self._ecomode = True
        self._autocontrol = True
        self._userpwm = 0
        self._safestop = False

    def _fan_setpwm(self, pwm):
        self._pwm = pwm
        wiringpi2.pwmWrite(self.PWM_PIN, pwm)

    def _fan_fullspeed(self):
        self._fan_setpwm(self.PWM_RANGE-1)

    def _fan_stop(self):
        self._fan_setpwm(0)

    def _read_fanload(self):
        # average over 100 samples
        m = self.kernel().get_supply().read(100)
        return m[1]

    def set_highest_profile(self):
        profile = self.PROFILES[-1]
        self.set_profile(profile)

    def set_lowest_profile(self):
        profile = self.PROFILES[0]
        self.set_profile(profile)

    def set_profile(self, newprofile):
        self._pid.set_ref(newprofile)

    def get_profile(self):
        return self._pid.get_ref()

    def _read_temp(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return float(f.readline()) / 1000.0
        except EnvironmentError:
            return None

    def _find_minspeed(self):
        # get idle load
        self._fan_stop()
        wiringpi2.delay(self.FAN_SPINUP)

        # find minimum
        self._idleload = self._read_fanload()

        # get full speed load
        self._fan_fullspeed()
        wiringpi2.delay(self.FAN_SPINUP)
        self._maxload = self._read_fanload() - self._idleload

        # find lowest pwm
        # 50% of maxload
        load_min = self._maxload * self.FAN_THRESHOLD
        # from highest to lowest
        minpwm = self.PWM_RANGE-1
        while minpwm != 0:
            self._fan_setpwm(minpwm)
            wiringpi2.delay(500)
            load = self._read_fanload() - self._idleload
            if load < load_min:
                break
            minpwm -= self.FAN_RECAL_PWM

        # turn fan off again
        self._fan_stop()

        if minpwm >= self.FAN_DEAD_PWM:
            self.loge("RIP FAN. It seems to be dead!")
            return False

        # update controller
        self._pid.set_coeff(self.PID_P, self.PID_I, self.PID_D)
        self._pid.set_limit(minpwm, self.PWM_RANGE-1)

        # update minspeed
        self._minpwm = minpwm
        self._minspeed = 100 * minpwm / (self.PWM_RANGE-1)
        self._caltime = self.time().jstimestamp()
        return True

    def _req_cpu_temp_profile(self, args, update):
        profile = args["profile"]

        if not update:
            if profile not in self.PROFILES:
                self.loge("New profile is not supported")
                return self.REQ_FAIL
            return self.req_statecheck(
                "cpu_temp_profile",
                self.get_profile() == profile
            )

        self.set_profile(profile)
        return self.REQ_PASS

    def _req_cpu_fan_user(self, args, update):
        speed = args["speed"]

        if not update:
            if speed < self._minpwm or speed > self.PWM_RANGE-1:
                self.loge("Speed is not in limits")
                return self.REQ_FAIL
            return self.req_statecheck(
                "fan_mode",
                self._autocontrol == False and self._userpwm == speed
            )

        self._autocontrol = False
        self._userpwm = speed
        return self.REQ_PASS

    def _req_cpu_fan_auto(self, args, update):
        if not update:
            return self.req_statecheck(
                "fan_mode",
                self._autocontrol == True
            )
        self._autocontrol = True
        self._userpwm = 0
        return self.REQ_PASS

    def startup_event(self, db, cfg):
        # config pwm
        wiringpi2.pinMode(self.PWM_PIN, wiringpi2.GPIO.PWM_OUTPUT)
        wiringpi2.pwmSetMode(wiringpi2.GPIO.PWM_MODE_MS)
        wiringpi2.pwmSetRange(self.PWM_RANGE)
        # 19.2 / 32 = 600KHz - Also starts the PWM
        wiringpi2.pwmSetClock(self.PWM_CLK_DIV)

        self.logd("Finding minimum fan speed...")
        if not self._find_minspeed():
            return False
        self.logd("Minimum fan speed: {}%".format(self._minspeed))

        self.set_highest_profile()
        # self.set_profile(40)
        if not self.add_requests([
            ["cpu_temp_profile", dict(profile="int")],
            ["cpu_fan_user", dict(speed="int")],
            ["cpu_fan_auto", dict()]
        ]):
            return False

        return True

    def run_event(self):
        time = self.time()

        temp = self._read_temp()
        if temp is None:
            self.loge("Failed to read CPU temperature")
            return False

        pidout = int(self._pid.compute(temp))

        if not self._autocontrol:
            self._fan_setpwm(self._userpwm)
        else:
            if self._ecomode:
                # should we leave eco mode?
                # yes if temp >= profile
                if temp >= self.get_profile():
                    self._ecomode = False
                    # turn on full speed
                    self._fan_fullspeed()
                    wiringpi2.delay(self.FAN_SPINUP)
                    self._fan_setpwm(pidout)
                else:
                    # turn(keep) fan off
                    self._fan_stop()
            else:
                # should we enter eco mode
                # yes if temp < profile - threshold
                if temp < (self.get_profile() - self.ECO_THRESHOLD):
                    self._ecomode = True
                    # turn off
                    self._fan_stop()
                else:
                    self._fan_setpwm(pidout)

        # log pwm as percent
        fanspeed = 100 * self._pwm / (self.PWM_RANGE-1)
        self._speedlog.log(time.jstimestamp(), fanspeed)
        self._templog.log(time.jstimestamp(), temp)
        return True

    # recalibrate at midnight
    def backup_event(self, db):
        if not self._find_minspeed():
            return False
        return True

    def report_event(self):
        return dict(
            temp=self._templog.serialize(),
            speed=self._speedlog.serialize(),
            fan=dict(
                automode=self._autocontrol,
                profiles=self.PROFILES,
                profile=self.get_profile(),
                minspeed=self._minspeed,
                ecomode=self._ecomode,
                maxload=self._maxload,
                calibration=self._caltime
            )
        )


    def shutdown_event(self):
        self._fan_stop()
