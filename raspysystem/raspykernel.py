# -*- coding: utf-8 -*-
import os
import argparse
import threading
import socket
import logging
import logging.handlers
import wiringpi2
import Queue
import sqlite3
import simplejson as json
from arrow import factory
from time import sleep
from HTMLParser import HTMLParser

from raspytask import RasPySimpleTask, RasPyTask
from raspytime import RasPyTime
from raspylogger import RasPyLogger
from raspysupplyreader import RasPySupplyReader
from raspysamplelogger import RasPySampleLogger

# PHP Frontend will add wrapper:
# prepend result string with error code
# {
#     success: true|false,
#     payload: { see ^ }|"error message string"
# }

# class RasPyPingPongCache(object):
#     def __init__(self):
#         self._active = 0
#         self._active_lock = threading.Lock()
#         self.buffers = [None, None]

#     def store(self, tsdata):
#         self.buffers[self._active] = tsdata

#         self._active_lock.acquire(True)
#         self._active ^= 1
#         self._active_lock.release()

#     def recall(self):
#         self._active_lock.acquire(True)
#         buf = self.buffers[self._active^1]
#         self._active_lock.release()
#         return buf

class RasPyKernel(RasPyLogger):
    VERSION_MAJOR = "3"
    VERSION_MINOR = "3"
    NAME = "RasPy"
    CODENAME = "HABICHT"

    LOGFILE = "info.log"
    CFGFILE = "config.json"
    SQLFILE = "master.sqlite"

    ERR_NONE = "E00"
    ERR_NOTRUNYET = "E01"
    ERR_NOTUPDATED = "E02"
    ERR_REQUEST_FAILED = "E03"
    ERR_INVALID_QUERY = "E04"

    QRY_REQUEST = "REQUEST"
    QRY_REPORT = "REPORT"
    QRY_PING = "PING"
    QRY_EXIT = "EXIT"

    SERVER_HOST = "localhost"
    SERVER_PORT = 1337


    # *MUST BE >= 60
    # *MUST BE <= 900 (15 min) > SOME TASKS EXPECT THIS
    # *15/PERIOD MUST BE INTEGER
    # + 1 min 60 s    @ 60 updates
    # + 3 min 180 s   @ 20 updates
    # + 5 min 300 s   @ 12 updates
    # + 15 min 900 s  @ 4 updates
    UPDATE_PERIOD = 60
    # tickrate for scheduler
    TICK_RATE = 1
    WATCHDOG_BUFFER = 10
    UPDATE_PERIOD_WTDG = UPDATE_PERIOD+WATCHDOG_BUFFER
    UPDATE_PERIOD_WARN = UPDATE_PERIOD-WATCHDOG_BUFFER
    MAX_SCHEDULE_DEVIATION = 5

    def __init__(self, path, debug):
        RasPyLogger.__init__(self, None, "kernel")

        self._debugmode = debug
        self._path = path
        self._configpath = os.path.join(self._path, self.CFGFILE)
        self._logpath = os.path.join(self._path, self.LOGFILE)
        self._databasepath = os.path.join(self._path, "database")
        self._resourcespath = os.path.join(self._path, "resources")

        self._running = True

        # scheduler specific
        self._scheduler_quit = threading.Event()
        self._scheduler_lock = threading.Lock()

        # shared, need scheduler_lock
        # tasks instances by task name
        self._tasks = dict()
        # tasks instances by priority
        self._taskschedule = list()
        # task response by task name
        self._caches = dict()
        # task response parts by task name
        self._cacheparts = dict()

        self._supply = RasPySupplyReader()
        self._timefactory = factory.ArrowFactory(RasPyTime)
        self._last_update = None
        self._current_update = None
        self._updates = 0
        self._runtime = 0
        self._instance_id = None
        # log totaltime over day
        self._totaltime = RasPySampleLogger(
            self.get_updates24h(),
            [5, 15, 60]
        )
        self._watchdog = None
        # in seconds
        self._timeout = 5
        self._float_decimals = 4

    # ++PICONTROL PROPERTIES BEGIN
    def get_supply(self):
        return self._supply

    def get_path(self):
        return self._path

    def get_databasepath(self):
        return self._databasepath

    def get_resourcespath(self):
        return self._resourcespath

    def get_timeout(self):
        return self._timeout

    def get_timefactory(self):
        return self._timefactory

    def get_period(self):
        return self.UPDATE_PERIOD

    def get_updates24h(self):
        return 24 * 60 * 60 / self.UPDATE_PERIOD

    def get_updates12h(self):
        return self.get_updates24h() / 2

    def get_updates6h(self):
        return self.get_updates24h() / 4

    # returns copy
    def get_time(self):
        return self._timefactory.get(
            self._current_update
        )
    # ++PICONTROL PROPERTIES END

    def serialize(self, data):
        return json.dumps(
            data,
            separators=(',', ':')
        )

    def get_tasks(self):
        return self._tasks

    def find_task(self, name):
        return self._tasks.get(name, None)

    def add_task(self, task):
        if task is None:
            return
        name = task.get_name()
        # add task and create cache
        self._tasks[name] = task
        self._caches[name] = str() # RasPyPingPongCache()
        self._cacheparts[name] = dict(
            info=str(),
            report=str(),
            request=str()
        )
        self._taskschedule.append(task)
        self.logd("Added task: {}".format(name))

    def _update_taskcachepart_info(self, taskname):
        task = self._tasks[taskname]
        cp = self._cacheparts[taskname]
        cp["info"] = self.serialize(
            dict(
                instance=self._instance_id,
                totaltime=self._totaltime.serialize(),
                runtime=self._runtime,
                tasktime=task.get_runtime(),
                timestamp=self._last_update.jstimestamp(),
                updates=self._updates,
                period=self.UPDATE_PERIOD
            )
        )

    def _update_taskcachepart_report(self, taskname):
        task = self._tasks[taskname]
        cp = self._cacheparts[taskname]
        cp["report"] = self.serialize(
            task.report()
        )

    def _update_taskcachepart_request(self, taskname):
        task = self._tasks[taskname]
        cp = self._cacheparts[taskname]
        cp["request"] = self.serialize(
            task.get_requests_simple()
        )

    # build cache from parts
    # beware: parts are already json strings
    def _update_taskcache(self, taskname):
        cp = self._cacheparts[taskname]
        newcache = "{"
        newcache += "\"info\":{}".format(cp["info"])
        newcache += ",\"report\":{}".format(cp["report"])
        newcache += ",\"request\":{}".format(cp["request"])
        newcache += "}"
        # self._caches[taskname].store(newcache)
        self._caches[taskname] = newcache

    def _report_task(self, taskname):
        return "{}{}".format(
            self.ERR_NONE,
            self._caches[taskname]
        )
        # cache = self._caches[taskname]
        # return "{}{}".format(
        #     self.ERR_NONE,
        #     cache.recall()
        # )

    def _request_task(self, taskname, command, arguments):
        task = self._tasks[taskname]

        # hex quotes to normal quotes
        h = HTMLParser()
        arguments = h.unescape(arguments)

        # arg is json object, parse it
        # frontend ensures valid json, check again just in case
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as e:
            self.loge("Invalid request arg json: {}".format(e))
            return self.ERR_REQUEST_FAILED

        # could be PASS; ADD; REMOVE which are OK
        if task.request(command, arguments) == RasPySimpleTask.REQ_FAIL:
            return self.ERR_REQUEST_FAILED

        # only update report
        self._update_taskcachepart_request(taskname)
        # update cache
        self._update_taskcache(taskname)
        return "{}{}".format(
            self.ERR_NONE,
            self._caches[taskname]
        )
        # return cache
        # cache = self._caches[taskname]
        # return "{}{}".format(
        #     self.ERR_NONE,
        #     cache.recall()
        # )

    def _scheduler_run_tasks(self):

        for task in self._taskschedule:
            self.logd("Run: {}".format(task.get_name()))
            if not task.run():
                self.loge("Fail: {}".format(task.get_name()))
                return False

        return True

    def _startup_tasks(self, config):
        conn = sqlite3.connect(
            os.path.join(self._databasepath, self.SQLFILE)
        )
        conn.row_factory = sqlite3.Row
        dbc = conn.cursor()

        for task in self._taskschedule:
            name = task.get_name()
            self.logd("Startup: {}".format(name))
            if not task.startup(dbc, config.get(name)):
                return False

        conn.commit()
        conn.close()
        return True

    def _shutdown_tasks(self):
        for task in self._taskschedule:
            task.shutdown()
            self.logd("Shutdown: {}".format(task.get_name()))

    def _backup_tasks(self):
        conn = sqlite3.connect(
            os.path.join(self._databasepath, self.SQLFILE)
        )
        conn.row_factory = sqlite3.Row
        dbc = conn.cursor()

        for task in self._taskschedule:
            self.logd("Backup: {}".format(task.get_name()))
            if not task.backup(dbc):
                self.logd("Fail: {}".format(task.get_name()))
                return False

        conn.commit()
        conn.close()
        return True


    def _execute_query(self, address, query):
        # no try except needed, since only php can access RasPy
        # and we make sure its a valid json input :)
        query = json.loads(query)
        query_type = query["type"]

        self.logd("Got Query: {}".format(query_type))

        if (
            query_type == self.QRY_REPORT or
            query_type == self.QRY_REQUEST
        ):

            # wait for scheduler to release
            # so we can access cache or add new requests
            self._scheduler_lock.acquire(True)

            updates = self._updates
            last_update = self._last_update

            req_timestamp = int(query["timestamp"])

            # scheduler has run?
            if not updates > 0:
                query_result = self.ERR_NOTRUNYET
            elif req_timestamp == last_update.jstimestamp():
                query_result = self.ERR_NOTUPDATED
            else:
                # front end ensures that task is valid!
                taskname = query["task"]
                if query_type == self.QRY_REPORT:
                    self.logd("Return: get report")
                    query_result = self._report_task(taskname)
                else:
                    self.logd("Return: set request + get report")
                    query_result = self._request_task(
                        taskname,
                        query["command"],
                        query["arguments"]
                    )

            self._scheduler_lock.release()

        elif query_type == self.QRY_PING:
            self.logd("Return: PING")
            query_result = self.ERR_NONE
        elif query_type == self.QRY_EXIT:
            self.logd("Return: EXIT")
            self._running = False
            query_result = self.ERR_NONE
        else:
            self.loge("Invalid Query: {}".format(query_type))
            query_result = self.ERR_INVALID_QUERY

        return query_result

    # send exit query to myself
    def _scheduler_send_exit_query(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect((self.SERVER_HOST, self.SERVER_PORT))
            s.send(self.serialize(dict(type=self.QRY_EXIT)))
            # dont care about response from myself :)
            # data = s.recv(256)
            s.close()
        except socket.error:
            pass

    def _scheduler_watchdog_event(self):
        self.loge("Scheduler has crashed")
        self._scheduler_send_exit_query()

    def _watchdog_start(self):
        self._watchdog = threading.Timer(
            self.UPDATE_PERIOD_WTDG,
            self._scheduler_watchdog_event
        )
        self._watchdog.start()

    def _watchdog_stop(self):
        self._watchdog.cancel()
        self._watchdog.join()

    def _scheduler_run(self):
        self._current_update = self._timefactory.now().norm()
        oldmin = self._current_update.minute
        timer = self.UPDATE_PERIOD

        # start watchdog now
        # attention: if new minute just started, we have to wait period*60s
        # and wd could overflow, but not with the buffer
        self._watchdog_start()
        while not self._scheduler_quit.is_set():

            # read supply
            self._supply.read_periodic()

            # sleep thread
            sleep(self.TICK_RATE)
            self._current_update = self._timefactory.now().norm()

            # another minute has passed?
            if oldmin == self._current_update.minute:
                continue

            oldmin = self._current_update.minute
            timer -= 60
            if timer != 0:
                continue

            # reset timer
            timer = self.UPDATE_PERIOD

            # restart watchdog
            self._watchdog_stop()
            self._watchdog_start()

            # backup at midnight
            if self._current_update.new_day():
                if not self._backup_tasks():
                    self._scheduler_send_exit_query()
                    break

            # process requests
            # do not let server add new requests
            self._scheduler_lock.acquire(True)
            for task in self._taskschedule:
                task.process_requests()
            self._scheduler_lock.release()

            dt = self._timefactory.now()
            # run tasks
            if not self._scheduler_run_tasks():
                self._scheduler_send_exit_query()
                break

            dt = self._timefactory.now() - dt
            runtime = dt.total_seconds()

            # update cache part: report
            # >reports can be hugh
            # >json dumps of reports *could* be slow
            # >total time should track this time too
            for taskname in self._tasks:
                self._update_taskcachepart_report(taskname)

            dt = self._timefactory.now() - self._current_update
            totaltime = dt.total_seconds()

            if totaltime > self.UPDATE_PERIOD_WARN:
                self.loge("Update period might be too low! need: {}".format(totaltime))
                for task in self._taskschedule:
                    self.loge("{}: {}".format(
                        task.get_name(),
                        task.get_runtime()
                    ))

                if totaltime > self.UPDATE_PERIOD:
                    self.loge("Update period is too low! Quitting.")
                    self._scheduler_send_exit_query()
                    break

            # reset supply samples
            self._supply.clear_samples()

            # wait for server to clear lock

            # 2do: this can lead to slow response times for server request/report
            # if task cache recreation takes much time (>1s)

            # we can change:
            # * scheduler states
            # * task caches
            self._scheduler_lock.acquire(True)
            self._updates += 1
            self._last_update = self._current_update
            self._runtime = runtime

            self._totaltime.log(
                self._current_update.jstimestamp(),
                totaltime
            )

            # update cache part: info+report
            # these should be *small*
            # finally update cache
            for taskname in self._tasks:
                self._update_taskcachepart_info(taskname)
                self._update_taskcachepart_request(taskname)
                self._update_taskcache(taskname)

            self._scheduler_lock.release()

        # stop watchdog
        self._watchdog_stop()

    def _start(self):
        # 1) setup logger
        if self._debugmode:
            # add stream handler
            loghandler = logging.StreamHandler()
            loghandler.setLevel(logging.DEBUG)
            loghandler.setFormatter(
                logging.Formatter("(%(name)s) %(message)s")
            )
        else:
            # add a rotating file handler, 10 kB
            # overwrite old log
            loghandler = logging.handlers.RotatingFileHandler(
                self._logpath,
                maxBytes=10*1024,
                backupCount=5
            )
            loghandler.setLevel(logging.WARNING)
            loghandler.setFormatter(
                logging.Formatter(
                    "%(levelname)s %(asctime)s (%(name)s) %(message)s",
                    "%d.%m.%y %H:%M:%S"
                )
            )

        self.get_logger().addHandler(loghandler)
        self.get_logger().setLevel(
            logging.DEBUG if self._debugmode else logging.WARNING
        )

        # start message
        self.logd("***{}({})***".format(self.NAME, self.CODENAME))
        self.logd("Version: {}.{}".format(self.VERSION_MAJOR, self.VERSION_MINOR))
        self.logd("Path: {}".format(self._path))
        self.logd("***{}***".format("*"*len(self.NAME)))


        # 2) open config
        try:
            with open(self._configpath, 'r') as stream:
                try:
                    config = json.load(stream)
                except json.JSONDecodeError as e:
                    self.loge("Config parse error: {}".format(e))
                    return False
        except EnvironmentError:
            self.loge("Can not find config file")
            return False


        # 3) setup supplyreader
        if not self._supply.setup():
            self.loge("Supply Reader Error")
            return False

        # 4) setup timeouts
        timeout = config.get("timeout")
        if timeout is not None:
            self._timeout = int(timeout)

        # 5) init wiringpi
        wiringpi2.wiringPiSetup()

        # 6) sort by tasks by elevated property
        # > non elevated get executed first
        self._taskschedule.sort(
            key=lambda task: (task.get_elevated())
        )

        # 7) startup tasks
        if not self._startup_tasks(config):
            return False

        # create unique startup time latch
        # so web app can detect a version change
        self._instance_id = self._timefactory.now().jstimestamp()
        return True

    def run(self):

        if not self._start():
            self.logd("Failed to start")
            return

        # start server
        self.logd("Starting Server")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.SERVER_HOST, self.SERVER_PORT))
        server_socket.listen(100)

        # start scheduler thread
        self.logd("Starting Scheduler")
        scheduler = threading.Thread(target=self._scheduler_run)
        scheduler.start()

        while self._running:
            # wait for a connection
            connection, address = server_socket.accept()
            request = connection.recv(256)
            response = self._execute_query(address, request)
            connection.send(response)
            connection.close()

        self.logd("Stopped Server")

        # terminate scheduler
        self._scheduler_quit.set()
        # wait for scheduler to stop
        scheduler.join()
        self.logd("Stopped Scheduler")

        # shutdown tasks
        self._shutdown_tasks()
        return True
