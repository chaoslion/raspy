# -*- coding: utf-8 -*-
import wiringpi2
from math import fsum


class RasPySupplyReader(object):
    ADC_NSS = 3
    RSHUNT = 0.1
    R_RATIO = 3.0 / 5.0
    ADC_RATIO = 3.3 / 4096.0
    V_RATIO = ADC_RATIO / R_RATIO

    def __init__(self):
        self._samples = [
            list(),
            list(),
            list()
        ]

    def get_samples(self):
        return self._samples

    def _adc_select(self):
        # output pull to ground
        wiringpi2.pinMode(self.ADC_NSS, wiringpi2.GPIO.OUTPUT)
        wiringpi2.digitalWrite(self.ADC_NSS, wiringpi2.GPIO.LOW)

    def _adc_deselect(self):
        # input, let external pull up drive to high
        wiringpi2.pinMode(self.ADC_NSS, wiringpi2.GPIO.INPUT)

    def _adc_read_channels(self):

        chdq = [
            chr(0x01) + chr(0xA0) + chr(0x00),
            chr(0x01) + chr(0xE0) + chr(0x00)
        ]
        val = [0, 0]

        for i in range(2):
            dq = chdq[i]

            self._adc_select()
            # wiringpi2.delayMicroseconds(1)
            wiringpi2.wiringPiSPIDataRW(0, dq)
            # wiringpi2.delayMicroseconds(1)
            self._adc_deselect()

            val[i] = (ord(dq[1]) << 8) | (ord(dq[2]) << 0)

        return val

    def read(self, averages=10):
        v0 = []
        v1 = []

        # average
        for i in range(averages):
            p = self._adc_read_channels()
            v0.append(p[0])
            v1.append(p[1])

        v0 = fsum(v0) / averages
        v1 = fsum(v1) / averages

        vd = (v1 - v0) * self.V_RATIO

        vin = v1 * self.V_RATIO
        cin = vd / self.RSHUNT
        pin = vin * cin

        return [vin, cin, pin]

    def read_periodic(self, averages=10):
        sample = self.read(averages)
        for i in range(len(self._samples)):
            self._samples[i].append(sample[i])

    def clear_samples(self):
        for slist in self._samples:
            del slist[:]

    def setup(self):
        if wiringpi2.wiringPiSPISetup(0, 900000) == -1:
            return False

        # disable nss pullups
        wiringpi2.pullUpDnControl(self.ADC_NSS, wiringpi2.GPIO.PUD_OFF)
        # cycle NSS to ensure state in adc chip
        self._adc_deselect()
        self._adc_select()
        self._adc_deselect()
        return True
