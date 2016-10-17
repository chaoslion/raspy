# -*- coding: utf-8 -*-
from pushbullet import Pushbullet
from util import Mailer
from raspysystem.raspytask import RasPyTask
from twitter import TwitterTask


"""
    send report end of day via email
    send reports to pushbullet
"""
class NotifierTask(RasPyTask):

    def __init__(self, parent):
        RasPyTask.__init__(self, parent, "notifier", True)

        self._mailer = None

        self._pushbullet = None
        self._pb_ignored_hosts = list()

        self._subtasks = [
            TwitterTask(self)
        ]

    def _notify_mail(self):
        time = self.time()
        if not time.is_endof_week():
            return

        # 2do..
        self._mailer.send("PIControl", "Hello World!")

    def _notify_pushbullet(self):
        # send bullet if a device goes on/off
        devices = self.find_worker("fritz")["devices"].get_devices()

        # get mobiles
        notify_devs = devices.find_type(LanDevice.TYPE_MOBILE)
        # remove excluded owners
        for host in self._pb_ignored_hosts:
            notify_devs = notify_devs.find_owner(host, True)

        went_online = notify_devs.went_on()
        went_offline = notify_devs.went_off()

        # no updates, dont send
        if (len(went_online) == 0) and (len(went_offline) == 0):
            return

        # create message
        msg = unicode()

        if len(went_online) > 0:
            msg += "online:\n"
            for dev in went_online:
                msg += "*{}\n".format(dev.get_owner())

        if len(went_offline) > 0:
            msg += "offline:\n"
            for dev in went_offline:
                msg += "*{}\n".format(dev.get_owner())

        push = self._pushbullet.push_note("RasPy", msg)

    def run_event(self):
        #self._notify_mail()
        # self._notify_pushbullet()
        return True

    def startup_event(self, db, cfg):
        # for item in ["pushbullet", "mail", "twitter"]:
        #     if not item in cfg:
        #         self.loge("config missing: {}".format(item))
        #         return False

        # if not "apikey" in cfg["pushbullet"]:
        #     self.loge("pushbullet missing apikey")
        #     return False

        # for item in ["server", "port", "user", "password", "sender", "recipients"]:
        #     if not item in cfg["mail"]:
        #         self.loge("mail missing: {}".format(item))
        #         return False

        # # mail
        # self._mailer = Mailer(
        #     cfg["mail"]["server"],
        #     int(cfg["mail"]["port"]),
        #     1.0,
        #     cfg["mail"]["user"],
        #     cfg["mail"]["password"],
        #     cfg["mail"]["sender"],
        #     cfg["mail"]["recipients"]
        # )

        # # pushbullet
        # self._pushbullet = Pushbullet(cfg["pushbullet"]["apikey"])
        # self._pb_ignored_hosts = cfg["pushbullet"].get("excluded", list())
        return True
