# -*- coding: utf-8 -*-
import logging

class RasPyLogger(object):

    TYPE_NORMAL = 0
    TYPE_CONFIG = 1
    TYPE_CRITICAL = 2

    def __init__(self, parent, name):
        self._logger = logging.getLogger(name)
        if parent is not None:
            self._logger = parent.get_logger().getChild(name)

    def _prepend_type(self, msg, logtype):
        if logtype == self.TYPE_CONFIG:
            return "Config: {}".format(msg)
        elif logtype == self.TYPE_CRITICAL:
            return "Critical: {}".format(msg)
        else:
            return msg

    def get_logger(self):
        return self._logger

    def logc(self, msg):
        self._logger.critical(msg)

    def logd(self, msg, logtype=TYPE_NORMAL):
        self._logger.debug(self._prepend_type(msg, logtype))

    def logi(self, msg, logtype=TYPE_NORMAL):
        self._logger.info(self._prepend_type(msg, logtype))

    def loge(self, msg, logtype=TYPE_NORMAL):
        self._logger.error(self._prepend_type(msg, logtype))

    def logw(self, msg, logtype=TYPE_NORMAL):
        self._logger.warning(self._prepend_type(msg, logtype))
