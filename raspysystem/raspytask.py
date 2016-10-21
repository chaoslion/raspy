# -*- coding: utf-8 -*-
import logging
import threading
import arrow
import simplejson as json
import types
from raspylogger import RasPyLogger

class RasPySimpleTask(RasPyLogger):

    REQ_FAIL = 0
    REQ_PASS = 1
    REQ_ADD = 2
    REQ_REMOVE = 3

    ARGTYPES = dict(
        none=[types.NoneType],
        int=[types.IntType],
        float=[types.FloatType],
        num=[types.IntType,types.FloatType],
        string=[types.StringType, types.UnicodeType],
        array=[types.ListType],
        dict=[types.DictType],
        bool=[types.BooleanType]
    )

    def __init__(self, parent, name):

        RasPyLogger.__init__(
            self,
            parent,
            name
        )

        self._name = name
        self._parent = parent
        self._request_descriptions = dict()
        self._requests = dict()

    def _config_expect(self, items, config):
        for item in items:
            if not item in config:
                self.loge("Missing {}".format(item), RasPyLogger.TYPE_CONFIG)
                return False
        return True

    # only return names as dict objects
    # "request" {
    #     "foobar": {},
    #     "subtask": {
    #         "foo1": {},
    #         "foo2": {}
    #     }
    # }
    def get_requests_simple(self):
        result = dict()
        for name in self._requests:
            result[name] = dict()
        return result

    def get_name(self):
        return self._name

    def parent(self):
        return self._parent

    def kernel(self):
        return self.parent().kernel()

    def time(self):
        return self.kernel().get_time()

    def period(self):
        return self.kernel().get_period()

    # used by request callbacks
    def req_add(self, name):
        return [self.REQ_ADD, name]

    def req_remove(self, name):
        return [self.REQ_REMOVE, name]

    def req_statecheck(self, name, state_unchanged):
        if state_unchanged:
            return self.req_remove(name)
        else:
            return self.req_add(name)
    #

    # used by task to add request
    def add_request(self, name, arguments):

        # check duplicates
        if name in self._request_descriptions:
            self.loge("Request is not unique")
            return False

        # check if task has the callback
        # def _req_<name>()
        callback_name = '_req_{}'.format(name)

        if not hasattr(self, callback_name):
            self.loge("Request callback not found")
            return False

        callback = getattr(self, callback_name)

        if not callable(callback):
            self.loge("Request callback not callable")
            return False

        self._request_descriptions[name] = [
            callback,
            arguments
        ]
        self.logd("Request added: {}".format(name))
        return True

    def add_requests(self, requests):
        for request in requests:
            if not self.add_request(request[0], request[1]):
                return False
        return True

    # called by scheduler
    def process_requests(self):
        for name, request in self._requests.iteritems():
            request[0](request[1], True)
        # all request processed
        self._requests.clear()

    # called by server
    def report(self):
        return self.report_event()

    # called by server
    def request(self, command, arguments):
        return self.request_event(command, arguments)

    # CALLBACK EVENTS

    # not a "real" callback since requests are handled automatically
    def request_event(self, command, arguments):

        if command not in self._request_descriptions:
            self.loge("Unknown command: {}".format(command))
            return self.REQ_FAIL

        reqinfo = self._request_descriptions[command]

        # parameter checks

        # 1) empty dict()/no arguments
        if not reqinfo[1]:
            # so is arg empty?
            if not (not arguments):
                self.loge("No arguments expected: {}".format(command))
                return self.REQ_FAIL
        else:
            # 2) check every key for its type
            for arg_name, arg_type in reqinfo[1].iteritems():
                # check name
                if arg_name not in arguments:
                    self.loge("Argument expected: {}".format(arg_name))
                    return self.REQ_FAIL
                # check type
                if type(arguments[arg_name]) not in self.ARGTYPES[arg_type]:
                    self.loge("Type {} invalid for: {}".format(
                        arg_type,
                        arg_name
                    ))
                    return self.REQ_FAIL

        # 3) it is a valid request!
        # so call the callback to create request identifier:
        # callback passed -> request would change state
        # callback failed -> request would not change state

        result = reqinfo[0](arguments, False)

        if result != self.REQ_FAIL:
            # unpack result
            result, identifier = result

            if result == self.REQ_ADD:
                # this would also overwrite equal successive requests
                # store callback and parameters, so we can call it later
                self._requests[identifier] = [reqinfo[0], arguments]
                self.logd("(re)adding request to todo list")
            else:
                self.logd("Removing request from todo list")
                # remove request if state would not change
                # None to protect pop when name is not in requests
                # alternative: if name in requests: pop(name)
                self._requests.pop(identifier, None)

        return result

    def startup_event(self, db, cfg):
        return True

    def backup_event(self, db):
        return True

    def shutdown_event(self):
        pass

    def report_event(self):
        return dict()

    def run_event(self):
        return True

class RasPyTask(RasPySimpleTask):

    def __init__(self, kernel, name, elevated=False):
    #, period=1, period_exact=True

        RasPySimpleTask.__init__(
            self,
            kernel,
            name
        )
        # self._period = period
        # self._period_exact = period_exact
        self._elevated = elevated
        self._runtime = 0
        self._subtasks = list()
        kernel.add_task(self)

    # shortcut to access subtasks
    def __getitem__(self, key):
        task = self.find_subtask(key)
        if task is not None:
            return task
        raise KeyError(key)

    def find_subtask(self, name):
        for task in self._subtasks:
            if task.get_name() == name:
                return task
        return None

    def get_runtime(self):
        return self._runtime

    def get_elevated(self):
        return self._elevated

    # run after subtasks
    def postrun_event(self):
        return True

    # overload
    def get_requests_simple(self):
        myreq = RasPySimpleTask.get_requests_simple(self)
        # merge with subtasks requests if not empty
        for task in self._subtasks:
            taskreq = task.get_requests_simple()
            if not (not taskreq):
                myreq[task.get_name()] = taskreq
        return myreq

    # overload, because my parent is the kernel
    def kernel(self):
        return self.parent()

    # overload
    def process_requests(self):
        RasPySimpleTask.process_requests(self)
        for task in self._subtasks:
            task.process_requests()

    # overload
    # bar -> request bar
    # foo.bar -> subtask foo request bar
    def request(self, command, arguments):

        # a request for me or a subtask?
        # frontend ensures a valid format
        tree = command.split(".")
        if len(tree) == 1:
            return RasPySimpleTask.request(self, tree[0], arguments)
        else:
            # find matching subtask by name
            task = self.find_subtask(tree[0])
            if task is None:
                self.loge("Unknown subtask for request: {}".format(tree[1]))
                return self.REQ_FAIL
            return task.request(tree[1], arguments)

    # overload
    def report(self):
        myreport = self.report_event()
        # merge with subtasks report if not empty
        for task in self._subtasks:
            taskreport = task.report()
            if not (not taskreport):
                myreport.update({task.get_name(): taskreport})
        return myreport

    def startup(self, db, cfg):

        self.startup_event(db, cfg)

        for task in self._subtasks:
            name = task.get_name()
            taskcfg = None if cfg is None else cfg.get(name)
            if not task.startup_event(db, taskcfg):
                return False

        return True

    def backup(self, db):
        if not self.backup_event(db):
            return False
        for task in self._subtasks:
            if not task.backup_event(db):
                return False
        return True

    def shutdown(self):
        self.shutdown_event()
        for task in self._subtasks:
            task.shutdown_event()

    def run(self):
        tf = self.kernel().get_timefactory()
        dt = tf.now()

        # run =========
        if not self.run_event():
            return False
        # run child events
        for task in self._subtasks:
            if not task.run_event():
                return False
        # =============

        # run post event
        if not self.postrun_event():
            return False

        dt = tf.now() - dt
        self._runtime = dt.total_seconds()
        return True
