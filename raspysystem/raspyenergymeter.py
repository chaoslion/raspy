# -*- coding: utf-8 -*-
import sqlite3
import os
import arrow
from raspysamplelogger import RasPySampleLogger

class RasPyEnergyMeter(object):

    def __init__(self, period, path, prefix):

        self._dbfile = os.path.join(
            path,
            "energy{}.sqlite".format(period)
        )
        self._dbprefix = prefix
        self._update_period = period

        self._wh_per_update = 0
        self._hour_cnt = 0
        self._day_cnt = 0
        self._week_cnt = 0
        self._month_cnt = 0
        self._total_cnt = 0

        self._day_wh_log = RasPySampleLogger(24)
        self._week_wh_log = RasPySampleLogger(7)
        self._month_wh_log = RasPySampleLogger(31)

        self._endof_hour = 0
        self._endof_day = 0
        self._endof_week = 0
        self._endof_month = 0

        self._synced = False
        # in seconds
        self._ton = 0
        self._toff = 0
        # timestamp
        self._tstart = None

    def _db_store_total(self, db):
        db.execute(
            "UPDATE '{}_total' SET {}, {}, {} WHERE rowid = 1".format(
                self._dbprefix,
                "'wh'=?",
                "'ton'=?",
                "'toff'=?"
            ),
            (
                self._total_cnt,
                self._ton,
                self._toff
            )
        )

    def _db_store_month(self, db):
        db.execute(
            "INSERT INTO '{}_month' ('wh') VALUES (?)".format(
                self._dbprefix
            ),
            (
                self._day_cnt,
            )
        )

    def _db_clear_month(self, db):
        db.execute(
            "DELETE FROM '{}_month'".format(
                self._dbprefix
            )
        )

    def _store_state(self, time):
        conn = sqlite3.connect(self._dbfile)
        db = conn.cursor()

        self._db_store_total(db)
        self._db_store_month(db)

        if time.new_month():
            self._db_clear_month(db)

        conn.commit()
        conn.close()

    def _sync_to_database(self, time):
        conn = sqlite3.connect(self._dbfile)
        conn.row_factory = sqlite3.Row
        db = conn.cursor()

        # create tables if not exist
        db.execute(
            "CREATE TABLE IF NOT EXISTS '{}_month' ({}, {})".format(
                self._dbprefix,
                "'id' INTEGER PRIMARY KEY",
                "'wh' FLOAT"
            )
        )

        db.execute(
            "CREATE TABLE IF NOT EXISTS '{}_total' ({}, {}, {}, {})".format(
                self._dbprefix,
                "'tstart' INTEGER PRIMARY KEY",
                "'ton' INTEGER",
                "'toff' INTEGER",
                "'wh' FLOAT"
            )
        )

        # load total, tstart and ton, toff
        db.execute(
            "SELECT * FROM '{}_total'".format(
                self._dbprefix
            )
        )

        dbr = db.fetchone()
        if dbr is None:
            # empty, add zero
            self._tstart = time.timestamp
            db.execute(
                "INSERT INTO '{}_total' {} VALUES {}".format(
                    self._dbprefix,
                    "('tstart', 'ton', 'toff', 'wh')",
                    "(?,?,?,?)"
                ),
                (
                    self._tstart,
                    0,
                    0,
                    0
                )
            )
        else:
            self._total_cnt = float(dbr["wh"])
            self._ton = int(dbr["ton"])
            self._toff = int(dbr["toff"])
            self._tstart = int(dbr["tstart"])

        # fill day log with 0 until current hour
        for hour in range(time.hour):
            ts = time.replace(hour=hour,minute=0)
            self._day_wh_log.log(ts.jstimestamp(), 0)

        # fill month log from database
        db.execute(
            "SELECT wh FROM '{}_month'".format(
                self._dbprefix
            )
        )
        result = db.fetchall()

        now_day = time.day-1
        whs = [ float(r["wh"]) for r in result ]
        wh_cnt = len(whs)

        # correct for not enough or too many database entries
        if wh_cnt != now_day:

            if wh_cnt < now_day:
                # we have less database entries then days in month
                # assume device was off at that time
                missing_whs = now_day - wh_cnt
            else:
                # we have more database entries then days in month
                # assume device was off at that time
                self._db_clear_month(db)
                missing_whs = now_day

            missing_whs = [0 for _ in range(missing_whs)]
            for _ in missing_whs:
                # assume device was off that day
                self._toff += 24 * 60 * 60 / self._update_period
                # at this point self._day_cnt is 0
                # store this to database
                self._db_store_month(db)

            whs.extend(missing_whs)

        # finally fill month log
        for day in range(now_day):
            wh = whs[day]
            ts = time.replace(day=day+1, hour=0, minute=0)
            self._month_cnt += wh
            self._month_wh_log.log(ts.jstimestamp(), wh)

        # fill week from month log
        now_weekday = time.isoweekday()-1
        while now_weekday > 0:
            day = now_day - now_weekday
            now_weekday -= 1
            # in case month started in middle of week
            if day < 0:
                continue
            wh = whs[day]
            ts = time.replace(day=day+1, hour=0, minute=0)
            self._week_cnt += wh
            self._week_wh_log.log(ts.jstimestamp(), wh)

        conn.commit()
        conn.close()

    def _approx_consum(self, atime, btime):
        dt = btime - atime
        return self._wh_per_update * dt.total_seconds() / self._update_period

    def update(self, time, power):

        if not self._synced:
            self._sync_to_database(time)
            self._synced = True

        if time.new_hour():
            self._day_wh_log.log(
                time.replace(hours=-1).jstimestamp(),
                self._hour_cnt
            )
            self._hour_cnt = 0

        if time.new_day():

            # backup state to db
            self._store_state(time)

            self._day_wh_log.clear()

            # add to week/month
            self._week_wh_log.log(
                time.replace(days=-1).jstimestamp(),
                self._day_cnt
            )

            self._month_wh_log.log(
                time.replace(days=-1).jstimestamp(),
                self._day_cnt
            )
            self._day_cnt = 0

        if time.new_week():
            self._week_wh_log.clear()
            self._week_cnt = 0


        if time.new_month():
            self._month_wh_log.clear()
            self._month_cnt = 0


        if power == 0:
            self._toff += self._update_period
        else:
            self._ton += self._update_period

        # accumulate counters
        self._wh_per_update = float(power) / self._update_period
        self._hour_cnt += self._wh_per_update
        self._day_cnt += self._wh_per_update
        self._week_cnt += self._wh_per_update
        self._month_cnt += self._wh_per_update
        self._total_cnt += self._wh_per_update


        # calc estimations
        end_of_hour = time.ceil('hour').norm()
        end_of_day = time.ceil('day').norm()
        end_of_week = time.ceil('week').norm()
        end_of_month = time.ceil('month').norm()

        self._endof_hour = self._hour_cnt + self._approx_consum(time, end_of_hour)
        self._endof_day = self._day_cnt + self._approx_consum(time, end_of_day)
        self._endof_week = self._week_cnt + self._approx_consum(time, end_of_week)
        self._endof_month = self._month_cnt + self._approx_consum(time, end_of_month)

    def serialize(self):
        return dict(
            current=self._wh_per_update,
            ton=self._ton,
            toff=self._toff,
            tstart=self._tstart,
            logs=dict(
                day=self._day_wh_log.serialize(),
                week=self._week_wh_log.serialize(),
                month=self._month_wh_log.serialize()
            ),
            approx=dict(
                hour=self._endof_hour,
                day=self._endof_day,
                week=self._endof_week,
                month=self._endof_month
            ),
            counters=dict(
                hour=self._hour_cnt,
                day=self._day_cnt,
                week=self._week_cnt,
                month=self._month_cnt,
                total=self._total_cnt
            )
        )

