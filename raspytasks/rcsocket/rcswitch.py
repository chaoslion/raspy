import wiringpi2


class Switch(object):

    def __init__(self):
        self._txcount = 0
        self._txtimestamp = None

    def get_txcount(self):
        return self._txcount

    def get_txtimestamp(self):
        return self._txtimestamp

    def switch_off(self, time, address):
        self.switch(time, address, False)

    def switch_on(self, time, address):
        self.switch(time, address, True)

    def switch(self, time, address, value):
        self._txtimestamp = time.jstimestamp()
        self._txcount += 1

    def hw_init(self):
        raise NotImplementedError()

    def is_valid_address(self, address):
        raise NotImplementedError()

    def parse_address(self, address):
        raise NotImplementedError()

# (minimal)translated from RCSwitch.cpp
class SwitchTypeB(Switch):
    MAX_GROUPS = 4
    MAX_CHANNEL = 4
    GROUPS = range(0,MAX_GROUPS)
    CHANNELS = range(0,MAX_CHANNEL)
    ALL = range(0,MAX_GROUPS*MAX_CHANNEL)



    # offset  addressrange
    # False   00 - 33
    # True    11 - 44
    def __init__(self, tx_pin, offset):
        Switch.__init__(self)

        self._address_offset = offset
        self._nPulseLength = 350
        self._nRepeatTransmit = 10
        self._pin = tx_pin
        self._last_txcode = 0


    def get_txcode(self):
        return self._last_txcode

    def hw_init(self):
        wiringpi2.pinMode(
            self._pin,
            wiringpi2.GPIO.OUTPUT
        )

    # [0-3][0-3]
    def is_valid_address(self, address):
        if len(address) != 2:
            return False
        group = int(address[0])
        channel = int(address[1])
        if self._address_offset:
            group -= 1
            channel -= 1
        return group in self.GROUPS and channel in self.CHANNELS


    # all methods are guaranteed to work
    # if is_valid_address was successfull
    def parse_address(self, address):
        group = int(address[0])
        channel = int(address[1])
        if self._address_offset:
            group -= 1
            channel -= 1
        return (group, channel)

    def _get_codeword(self, group, channel, status):
        # if not (0 <= group < self.MAX_GROUPS) and not (0 <= channel < self.MAX_CHANNEL):
        #     return None
        code = ["0FFF", "F0FF", "FF0F", "FFF0"]

        result = code[group]
        result += code[channel]
        result += "FFF"
        result += "F" if status else "0"
        return result

    def _transmit(self, high_pulses, low_pulses):
        wiringpi2.digitalWrite(self._pin, wiringpi2.GPIO.HIGH)
        wiringpi2.delayMicroseconds(self._nPulseLength * high_pulses)
        wiringpi2.digitalWrite(self._pin, wiringpi2.GPIO.LOW)
        wiringpi2.delayMicroseconds(self._nPulseLength * low_pulses)

    def _sendt0(self):
        self._transmit(1, 3)
        self._transmit(1, 3)

    def _sendt1(self):
        self._transmit(3, 1)
        self._transmit(3, 1)

    def _sendtf(self):
        self._transmit(1, 3)
        self._transmit(3, 1)

    def _sendsync(self):
        self._transmit(1, 31)

    def _send_tristate(self, scode):
        for i in range(0, self._nRepeatTransmit):
            for c in scode:
                if c == "0":
                    self._sendt0()
                elif c == "1":
                    self._sendt1()
                else:
                    self._sendtf()
            self._sendsync()

    def switch(self, time, address, value):
        Switch.switch(self, time, address, value)

        group, channel = self.parse_address(address)
        tx_code = self._get_codeword(group, channel, value)

        self._send_tristate(tx_code)
        self._last_txcode = tx_code
