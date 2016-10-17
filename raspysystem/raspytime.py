# -*- coding: utf-8 -*-
import arrow

# class which has time information
# downto minute
# eg 12.12.2012 12:12:00

class RasPyTime(arrow.Arrow):

    def norm(self):
        return self.replace(second=0, microsecond=0)

    # dont use javascript timestamp for now!
    # because php can't handle > 32bit ints on RasPi
    # the json_decode/encode functions have to
    # store them as float or string -> might be
    # a performance issue. have to look
    # def jstimestamp(self):
    #     return self.timestamp * 1000
    def jstimestamp(self):
        return self.timestamp

    # the following methods only make sense
    # if called every minute, hour etc
    def every_quarter(self):
        return self.minute in (0, 15, 30, 45)

    def every_half(self):
        return self.minute in (0, 30)

    def every_12hrs(self):
        return (
            self.new_hour() and
            self.hour in (0, 12)
        )

    def every_6hrs(self):
        return (
            self.new_hour() and
            self.hour in (0, 6, 12, 18)
        )

    def every_3hrs(self):
        return (
            self.new_hour() and
            self.hour in (
                0, 3, 6, 9,
                12, 15, 18, 21
            )
        )

    def quarter_past(self):
        return self.minute == 15

    def half_past(self):
        return self.minute == 30

    def quarter_to(self):
        return self.minute == 45

    def new_hour(self):
        return self.minute == 0

    def new_day(self):
        return self.hour == 0 and self.minute == 0

    def new_week(self):
        return (
            self.weekday() == 0 and
            self.hour == 0 and
            self.minute == 0
        )

    def new_month(self):
        return (
            self.day == 1 and
            self.hour == 0 and
            self.minute == 0
        )

    # xxx, xx:59
    def endof_hour(self):
        return (
            self.minute == 59
        )

    # xxx, 23:59
    def endof_day(self):
        return (
            self.hour == 23 and
            self.minute == 59
        )

    # sun, 23:59
    def endof_week(self):
        return (
            self.weekday() == 6 and
            self.hour == 23 and
            self.minute == 59
        )

    # sun, 23:59
    def endof_week(self):
        return (
            self.weekday() == 6 and
            self.hour == 23 and
            self.minute == 59
        )

    def endof_month(self):
        dx = self.ceil('month').day
        return (
            self.day == dx and
            self.hour == 23 and
            self.minute == 59
        )

    # 02:30
    def _parse_tstr(self, tstr):
        hrs = int(tstr[0]) * 10
        hrs += int(tstr[1])

        if not (0 <= hrs <= 23):
            raise ValueError()

        if tstr[2] != ':':
            raise ValueError()

        mins = int(tstr[3]) * 10
        mins += int(tstr[4])

        if not (0 <= mins <= 59):
            raise ValueError()

        return (hrs, mins)

    def gt(self, tstr):
        h, m = self._parse_tstr(tstr)
        return self > self.replace(hour=h, minute=m)

    def ge(self, tstr):
        h, m = self._parse_tstr(tstr)
        return self >= self.replace(hour=h, minute=m)

    def lt(self, tstr):
        h, m = self._parse_tstr(tstr)
        return self < self.replace(hour=h, minute=m)

    def le(self, tstr):
        h, m = self._parse_tstr(tstr)
        return self <= self.replace(hour=h, minute=m)

    def eq(self, tstr):
        h, m = self._parse_tstr(tstr)
        return self == self.replace(hour=h, minute=m)
