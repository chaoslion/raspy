# -*- coding: utf-8 -*-
import requests
import tweepy
from raspysystem.raspysamplelogger import RasPySampleLogger
from raspysystem.raspytask import RasPySimpleTask

# import raspytasks.fritz.landevice
import raspytasks.sensor.sensor
import raspytasks.supply.task

# *send tweet every hour about status
# *at 06:00 morning announcement
# *at 18:00 evening announcement
class TwitterTask(RasPySimpleTask):

    TWITTER_NAME = "PIC"
    SUMMARY_MAXLEN = 10
    EMOJIS = dict(
        # weather
        nightstars=u"\U0001F303",
        sunwrays=u"\U00002600",
        sunface=u"\U0001F31E",
        rain=u"\U0001F327",
        snow=u"\U0001F328",
        wind=u"\U0001F4A8",
        foggy=u"\U0001F301",
        cloud=u"\U00002601",
        cloudpart=u"\U000026C5",
        sunrise=u"\U0001F305",
        thunder=u"\U000026C8",
        volcano=u"\U0001F30B",
        # smileys
        sleep=u"\U0001F634",
        fingerup=u"\U0000261D",
        thinking=u"\U0001F914",
        okhand=u"\U0001F44C",
        # etc
        battery=u"\U0001F50B",
        graph=u"\U0001F4C8",
        cam=u"\U0001F4F7",
        arrowup=u"\U00002B06",
        arrowdn=u"\U00002B07"
    )

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "twitter")

        self._active = True
        self._tweepy = None
        self._tweets = 0
        self._last_tweet = None
        self._status = None

    def startup_event(self, db, cfg):
        if not self._config_expect(["consumer", "access"], cfg):
            return False

        auth = tweepy.OAuthHandler(
            cfg["consumer"][0],
            cfg["consumer"][1]
        )
        auth.set_access_token(
            cfg["access"][0],
            cfg["access"][1]
        )
        self._tweepy = tweepy.API(
            auth,
            timeout=self.kernel().get_timeout()
        )

        if not self.add_requests([
            ["pause", dict()],
            ["unpause", dict()]
        ]):
            return False

        return True

    def _req_pause(self, args, update):
        if not update:
            return self.req_statecheck(
                "active",
                self._active == False
            )
        self._active = False
        return self.REQ_PASS

    def _req_unpause(self, args, update):
        if not update:
            return self.req_statecheck(
                "active",
                self._active == True
            )
        self._active = True
        return self.REQ_PASS

    def run_event(self):
        time = self.time()

        if not time.new_hour() or not self._active:
            return True

        msg = unicode()
        msg_time = unicode()

        webcam_file = None

        # min_system = self.kernel().find_task("system")
        task_supply = self.kernel().find_task("supply")
        task_weather = self.kernel().find_task("weather")
        task_sensor = self.kernel().find_task("sensor")


        msg_time += unicode(u"Es ist {}Uhr\n").format(time.format("HH:mm"))


        # from ]06:00-18:00[ append webcam image
        # at 06:00/18:00 append sunrise/sunset

        if time.eq("06:00"):
            msg += unicode(u"Guten Morgen!\n")
            msg += msg_time

            # current date as string
            # msg += "Es ist {} Uhr am {} den {}.\n".format(
            #     time.format("hh:mm"),
            #     time.format("dddd", locale="de"),
            #     time.format("DD.MM.YYYY")
            # )

            # try to get sunrise
            wd = task_weather["forecast"].find_daily(time.day)
            if wd is not None:
                # convert to local time
                sunrise = wd.sunriseTime.to('local')
                msg += unicode(u"{}{} {} um {}Uhr.\n").format(
                    self.EMOJIS["sunface"],
                    self.EMOJIS["arrowup"],
                    "war" if time >= sunrise else "ist",
                    sunrise.format("HH:mm")
                )

            msg += unicode(u"Schalte{}an!\n").format(self.EMOJIS["cam"])

        elif time.eq("18:00"):
            msg += unicode(u"Guten Abend!\n")
            msg += msg_time

            # try to get sunrise
            wd = task_weather["forecast"].find_daily(time.day)
            if wd is not None:
                # convert to local time
                sunset = wd.sunsetTime.to('local')
                msg += unicode(u"{}{} {} um {}Uhr.\n").format(
                    self.EMOJIS["sunface"],
                    self.EMOJIS["arrowdn"],
                    "war" if time >= sunset else "ist",
                    sunset.format("HH:mm")
                )

            msg += unicode(u"Genug fotografiert.{}\n").format(self.EMOJIS["fingerup"])
            # msg += u"Anbei der heutige Zeitraffer.\n"
            # msg += u" Ich passe auf{}\n".format(self.EMOJIS["fingerup"])


        else:
            msg += msg_time

            if task_weather["cam"].get_video_online():
                webcam_file = task_weather["cam"].get_image_file()

            currently = task_weather["forecast"].get_currently()
            if currently is not None:
                # map state to emoji
                if currently.icon == "clear-day":
                    emoji = self.EMOJIS["sunwrays"]

                elif currently.icon == "clear-night":
                    emoji = self.EMOJIS["nightstars"]

                elif currently.icon == "rain":
                    emoji = self.EMOJIS["rain"]

                elif (
                    currently.icon == "snow" or
                    currently.icon == "sleet" ):
                    emoji = self.EMOJIS["snow"]

                elif currently.icon == "wind":
                    emoji = self.EMOJIS["wind"]

                elif currently.icon == "fog":
                    emoji = self.EMOJIS["foggy"]

                elif currently.icon == "cloudy":
                    emoji = self.EMOJIS["cloud"]

                elif(
                    currently.icon == "partly-cloudy-day" or
                    currently.icon == "partly-cloudy-night" ):
                    emoji = self.EMOJIS["cloudpart"]
                else:
                    emoji = unicode()

                if currently.summary is not None:

                    # include website link if summary is too long
                    if len(currently.summary) > self.SUMMARY_MAXLEN:
                        summary = unicode(u"{}{}".format(
                            currently.summary[0:self.SUMMARY_MAXLEN-3],
                            "..."
                        ))
                    else:
                        summary = unicode(currently.summary)
                else:
                    summary = unicode()


                msg += unicode(u"{}{}\n").format(
                    emoji,
                    summary
                )

        # append task data
        temp_sensors = task_sensor.get_sensors()["temp"]
        tin = temp_sensors["Arbeitszimmer"]["wand"].get_value()
        tout = temp_sensors["Innenhof"]["fenster"].get_value()
        if not (tin is None):
            msg += unicode(u"Ti:{}°C\n").format(round(tin, 2))
        if not (tout is None):
            msg += unicode(u"Ta:{}°C\n").format(round(tout, 2))

        # supply
        supply_stats = task_supply.get_hourly_stats()
        supply_stats_emoji = list()
        for supply_ui in supply_stats[0:2]:

            if supply_ui[1] == raspytasks.supply.task.SupplyTask.SUPPLY_OK:
                supply_str = self.EMOJIS["okhand"]
            elif supply_ui[1] == raspytasks.supply.task.SupplyTask.SUPPLY_HI:
                supply_str = u">{}".format(self.EMOJIS["thinking"])
            else:
                supply_str = u"<{}".format(self.EMOJIS["thinking"])

            supply_stats_emoji.append(supply_str)

        msg += unicode(u"Vdd:{}V{}\n").format(round(supply_stats[0][0], 2), supply_stats_emoji[0])
        msg += unicode(u"Idd:{}A{}\n").format(round(supply_stats[1][0], 2), supply_stats_emoji[1])
        msg += unicode(u"Pdd:{}W\n").format(round(supply_stats[2][0], 2))

        try:
            media = list()

            if webcam_file is not None:
                image = self._tweepy.media_upload(webcam_file)
                media.append(image.media_id)

            # msg += unicode(u"^{}".format(self.TWITTER_NAME))
            self._tweepy.update_status(
                status=msg,
                media_ids=media
            )
            self._tweets += 1
            self._last_tweet = time.jstimestamp()
            self._status = "OK"

        except requests.exceptions.RequestException as e:
            self.loge(e)
            return False
        except tweepy.TweepError as e:
            self._status = "twitter error"
            self.loge("Twitter error: {}".format(e))

        return True

    def report_event(self):
        return dict(
            tweets=self._tweets,
            last_tweet=self._last_tweet,
            status=self._status
        )
