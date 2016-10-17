# -*- coding: utf-8 -*-
import os
import shutil
import base64
import zlib
import time
import random
from collections import deque
from StringIO import StringIO
import subprocess
import threading

from PIL import Image, ImageFilter, ImageFont, ImageDraw

import pygame.draw
import pygame.font
import pygame.camera
import pygame.surface
import pygame.transform


from raspysystem.raspytask import RasPySimpleTask
from cam_tools  import Skydetector

class PingPongFile(object):

    def __init__(self, path, basename, extension):
        self._dst = 0
        self._basename = basename
        self._extension = extension
        self._path = path

    def get_write(self):
        return self._dst

    def get_read(self):
        return self._dst ^ 1

    def get_basename(self):
        return os.path.join(
            self._path,
            self._basename
        )

    def change(self):
        self._dst ^= 1

    def write_change(self):
        filename = self.write()
        self.change()
        return filename

    def write(self):
        return os.path.join(
            self._path,
            "{}{:02d}{}".format(
                self._basename,
                self._dst,
                self._extension
            )
        )

    def read(self):
        return os.path.join(
            self._path,
            "{}{:02d}{}".format(
                self._basename,
                self._dst ^ 1,
                self._extension
            )
        )

    def change(self):
        self._dst ^= 1


class CameraProcessor(object):
    EXPOSURE_DELAY = 5
    VIDEO_RATE = 2
    # 4 fph * 12 = 48
    VIDEO_DURATION = 48
    OFFSET = 10
    # colors
    BLACK = (0,0,0)
    RED = (255,0,0)
    WHITE = (255,255,255)
    GRAY = (128, 128, 128)

    # 0%-100% = 101 values, add 1
    # to make it multiple of 2
    HISTOGRAM_HEIGHT = 102
    HISTOGRAM_WIDTH_SCALE = 2

    def __init__ (self, media_path, device, fonts):
        self._avconv = None
        self._device = device
        self._fonts = fonts

        self._thread = None
        self._media_path = media_path

        resolution = device.get_size()

        self._sky_detector = Skydetector(resolution)
        self._cam_py = pygame.surface.Surface(resolution)

        # main background
        self._image_pil = Image.new(
            "RGB",
            (
                resolution[0],
                resolution[1] + self.HISTOGRAM_HEIGHT
            )
        )

        # files
        self._online_file = PingPongFile(media_path, "web", ".png")
        self._sky_file = PingPongFile(media_path, "websky", ".png")
        self._offline_file = PingPongFile(media_path, "weboff", ".png")
        self._video_file = PingPongFile(media_path, "weblapse", ".mp4")

    def get_image(self):
        return self._image_pil

    def get_online_file(self):
        return self._online_file

    def get_offline_file(self):
        return self._offline_file

    def get_video_file(self):
        return self._video_file

    def initial(self):
        # generate image files
        for index in range(self.VIDEO_DURATION):
            self._store_image_video(index)

        self._store_image_online()
        self._store_image_offline()

        # generate video
        self._generate_webcam_video()

    def _generate_webcam_video(self):

        args = [
            "avconv",
            "-y",
            "-f",
            "image2",
            "-r",
            "{}".format(self.VIDEO_RATE),
            "-i",
            "{}/weblapse%02d.png".format(self._media_path),
            self._video_file.write()
        ]
        # run avconv and wait for completion
        with open(os.devnull, 'w') as devnull:
            subprocess.call(
                args,
                stdout=devnull,
                stderr=devnull
            )

    def _store_image_video(self, index):
        self._image_pil.save(
            "{}/weblapse{:02d}.png".format(
                self._media_path,
                index
            ),
            'PNG',
            compress_level=4
        )

    def _store_image_online(self):
        # store file for lapse

        # move file queue
        for i in range(self.VIDEO_DURATION-1):
            filename_new = os.path.join(
                self._media_path,
                "weblapse{:02d}.png".format(i)
            )
            filename_old = os.path.join(
                self._media_path,
                "weblapse{:02d}.png".format(i + 1)
            )
            os.rename(filename_old, filename_new)

        # store latest image
        self._store_image_video(self.VIDEO_DURATION-1)

        # and again as a static image
        self._image_pil.save(
            self._online_file.write_change(),
            'PNG',
            compress_level=4
        )

        # draw skyimg over unedited image
        skyimg = self._sky_detector.get_image()
        self._image_pil.paste(skyimg, (0,0) + skyimg.size)

        # store sky
        self._image_pil.save(
            self._sky_file.write_change(),
            'PNG',
            compress_level=4
        )


    def _store_image_offline(self):
        # store offline
        self._image_pil.save(
            self._offline_file.write_change(),
            'PNG',
            compress_level=4
        )

    def _draw_description(self, text):

        if not len(text):
            return

        # make this image rgba and blend it over original image
        # img = Image.new("RGBA", self._image_pil.size, (255,255,255,0))
        # draw = ImageDraw.Draw(img)

        draw = ImageDraw.Draw(self._image_pil)

        ta = draw.textsize(text, font=self._fonts["description"])
        # trim if width is too long ?

        # location: lower center
        img_size = self._image_pil.size
        x = img_size[0] / 2 - ta[0] / 2
        #y = img_size[1] - self.HISTOGRAM_HEIGHT - ta[1] - self.OFFSET
        y = img_size[1] - self.HISTOGRAM_HEIGHT - ta[1]
        draw.text((x, y), text, font=self._fonts["description"], fill="#ff0000")

    def _draw_info(self, imgtime, rendertime):
        date_str = imgtime.format("DD.MM.YY")
        time_str = imgtime.format("HH:mm")
        seq_str = "#{:02}".format(self._online_file.get_write())
        rend_str = "{}s".format(round(rendertime, 2))

        draw = ImageDraw.Draw(self._image_pil)

        area_time = draw.textsize(time_str, font=self._fonts["big"])
        area_date = draw.textsize(date_str, font=self._fonts["small"])
        area_seq = draw.textsize(seq_str, font=self._fonts["small"])
        area_rend = draw.textsize(rend_str, font=self._fonts["small"])

        img_size = self._image_pil.size

        x = (
            img_size[0] -
            max(
                area_time[0],
                area_date[0],
                area_seq[0],
                area_rend[0]) -
            self.OFFSET
        )

        y = (
            img_size[1] -
            area_time[1] -
            area_date[1] -
            area_seq[1] -
            area_rend[1] -
            self.OFFSET
        )

        if x < 0 or y < 0:
            return

        # time
        draw.text((x, y), time_str, font=self._fonts["big"], fill=self.WHITE)
        # date
        y += area_time[1]
        draw.text((x, y), date_str, font=self._fonts["small"], fill=self.WHITE)
        # seq
        y += area_seq[1]
        draw.text((x, y), seq_str, font=self._fonts["small"], fill=self.WHITE)
        # render time
        y += area_rend[1]
        draw.text((x, y), rend_str, font=self._fonts["small"], fill=self.WHITE)



    def _draw_online(self):
        resolution = self._device.get_size()

        # start capturing
        self._device.start()
        # take a few snaps and wait for camera
        # exposure controller to settle
        for _ in range(self.EXPOSURE_DELAY):
            self._device.get_image(self._cam_py)
            time.sleep(1)

        # stop capturing
        self._device.stop()

        # convert to pil image
        raw = pygame.image.tostring(self._cam_py, "RGB")
        cam_pil = Image.frombytes("RGB", resolution, raw)


        # blur neighbourhood at pos (450, 300)[@640, 480]
        blur_pos_at640480 = (449, 349)
        # scale to resolution
        blur_pos = (
            int(round(blur_pos_at640480[0] * resolution[0] / 640.0)),
            int(round(blur_pos_at640480[1] * resolution[1] / 480.0))
        )
        blur_area = blur_pos + (resolution[0]-1, resolution[1]-1)
        blur_pil = cam_pil.crop(blur_area).filter(ImageFilter.GaussianBlur(radius=6))


        # calc skyboxes
        self._sky_detector.detect(cam_pil, blur_area)

        # BW histogram:
        hist = cam_pil.convert('L').histogram()
        h_max = max(hist)
        # calc rel values
        hist = [100.0 * g / h_max for g in hist]
        histo_ybase = self._image_pil.size[1] - 1

        # RGB histogram:
        # hist = image_pil.histogram()
        # hr = hist[0:256]
        # hg = hist[256:512]
        # hb = hist[512:768]

        # # find max
        # h_max = max(max(hr), max(hg), max(hb))
        # # calc rel histogram
        # hr = [100.0 * r / h_max for r in hr]
        # hg = [100.0 * g / h_max for g in hg]
        # hb = [100.0 * b / h_max for b in hb]


        # # render histogram
        # # fill histogram background with white
        # # histogram_area = (0, resolution[1], 512, self.HISTOGRAM_HEIGHT)
        # histo_ybase = self._image_py.get_size()[1] - 1
        # for x in range(256):
        #     x_real = x * 2

        #     hist2col = [
        #         [2 * self.HISTOGRAM_HEIGHT, int(round(hr[x])), 0xFF0000],
        #         [1 * self.HISTOGRAM_HEIGHT, int(round(hg[x])), 0x00FF00],
        #         [0 * self.HISTOGRAM_HEIGHT, int(round(hb[x])), 0x0000FF]
        #     ]

        #     # line from base to count value
        #     for hc in hist2col:

        #         pygame.draw.line(
        #             self._image_py, hc[2],
        #             (x_real, histo_ybase - hc[0]),
        #             (x_real, histo_ybase - hc[0] - hc[1])
        #         )

        #         pygame.draw.line(
        #             self._image_py, hc[2],
        #             (x_real + 1, histo_ybase - hc[0]),
        #             (x_real + 1, histo_ybase - hc[0] - hc[1])
        #         )
        # clear
        self._image_pil.paste((0, 0, 0))
        # draw cam image
        self._image_pil.paste(cam_pil, (0, 0) + cam_pil.size)

        # draw blur
        self._image_pil.paste(blur_pil, blur_area)

        # draw histogram
        draw = ImageDraw.Draw(self._image_pil)
        for x in range(256):
            x_real = x * self.HISTOGRAM_WIDTH_SCALE
            h = int(round(hist[x]))

            draw.line(
                (x_real, histo_ybase, x_real, histo_ybase - h),
                fill=self.GRAY
            )
            draw.line(
               (x_real + 1, histo_ybase, x_real + 1, histo_ybase - h),
                fill=self.GRAY
            )

    def _draw_offline(self):
        resolution = self._device.get_size()

        # clear
        self._image_pil.paste((0, 0, 0))
        # draw cross
        draw = ImageDraw.Draw(self._image_pil)
        draw.line(
            (0, 0, resolution[0], resolution[1]),
            fill=self.RED
        )
        draw.line(
            (resolution[0], 0, 0, resolution[1]),
            fill=self.RED
        )

    def processing(self):
        if not (self._thread is None):
            return self._thread.is_alive()
        return False

    def process(self, online, description, imgtime):
        self._thread = threading.Thread(target=self.run, args=(online, description, imgtime))
        self._thread.start()

    def run(self, online, description, imgtime):
        render_time = time.time()
        if online:
            self._draw_online()
        else:
            self._draw_offline()
        render_time = time.time() - render_time
        # add description+info
        self._draw_description(description)
        self._draw_info(imgtime, render_time)

        if online:
            self._store_image_online()
            self._generate_webcam_video()
        else:
            self._store_image_offline()


class CameraTask(RasPySimpleTask):
    SUMMARY_MAXLEN = 30
    FONT_SIZE_BIG = 30
    FONT_SIZE_SMALL = 20
    # W, H MUST BE EVEN NUMBERS (why again?)
    # RESOLUTION = (800, 600)
    RESOLUTION = (640, 480)

    def __init__(self, parent):
        RasPySimpleTask.__init__(self, parent, "cam")


        # self._b64history = deque(maxlen=self.TIMELAPSE_LENGTH)
        # load  font
        pygame.font.init()
        # load camera
        pygame.camera.init()

        self._camera_process = None
        # pygame camera device
        self._device = None

        self._media_path = None
        self._video_online = False

        # file mirrors from camera processing
        self._online_file = None
        self._offline_file = None
        self._video_file = None

    def get_video_online(self):
        return self._video_online

    def get_image_file(self):
        if self._video_online:
            return self._online_file.read()
        return self._offline_file.read()

    def startup_event(self, db, cfg):
        if not self._config_expect(["device"], cfg):
            return False

        deviceid = cfg["device"]

        path = self.kernel().get_path()
        self._media_path = os.path.join(
            path,
            "webcam"
        )

        if not os.path.exists(self._media_path):
            self.loge("Webcam image folder was not found")
            return False

        # load font
        path = self.kernel().get_resourcespath()
        path = os.path.join(path, "fonts")


        fonts = [
            "lobster.ttf",
            "sourcecode.ttf"
        ]

        font_files = [
            os.path.join(path, f) for f in fonts
        ]

        for font in font_files:
            if not os.path.exists(font):
                self.loge("Missing Font: {}".format(font))
                return False

        # init camera
        # cams = pygame.camera.list_cameras()
        # if len(cams) == 0:
        #     self.loge("no cameras found")
        #     return False

        self._device = pygame.camera.Camera(
            "/dev/video{}".format(deviceid),
            self.RESOLUTION,
            "RGB"
        )

        w, h = self._device.get_size()
        if w!=self.RESOLUTION[0] or h!=self.RESOLUTION[1]:
            self.loge("Invalid camera resolution")
            return False

        # turn focus off
        subprocess.call([
            "v4l2-ctl",
            "-d{}".format(deviceid),
            "-c", "focus_auto=0",
        ])

        subprocess.call([
            "v4l2-ctl",
            "-d{}".format(deviceid),
            "-c", "focus_absolute=0"
        ])

        # clear media folder
        for f in os.listdir(self._media_path):
            if not f.startswith("web"):
                continue
            f = os.path.join(self._media_path, f)
            os.remove(f)

        self._camera_process = CameraProcessor(
            self._media_path,
            self._device,
            dict(
                description = ImageFont.truetype(font_files[0], self.FONT_SIZE_BIG),
                big = ImageFont.truetype(font_files[1], self.FONT_SIZE_BIG),
                small = ImageFont.truetype(font_files[1], self.FONT_SIZE_SMALL)
            )
        )
        self.logd("Creating initial data")
        self._camera_process.initial()
        return True

    def run_event(self):
        time = self.time()

        # always check if image generation is done
        if not self._camera_process.processing():
            self._online_file = self._camera_process.get_online_file()
            self._offline_file = self._camera_process.get_online_file()
            self._video_file = self._camera_process.get_online_file()

        # always set video_online state
        self._video_online = time.ge("06:00") and time.lt("18:00")

        # generate webcam image every 15min
        if not time.every_quarter():
            return True

        description = unicode()

        if self._video_online:
            # get weather info
            # forecast runs before cam, so we use recent data
            cw = self.parent()["forecast"].get_currently()
            if cw is not None:

                # limit length
                if len(cw.summary) > self.SUMMARY_MAXLEN:
                    description = cw.summary[0:self.SUMMARY_MAXLEN] + "..."
                else:
                    description = cw.summary
        else:
            # calc time till camera goes back online
            if time.ge("18:00") and time.le("23:59"):
                ton = time.replace(days=+1,hour=6,minute=0)
            else:
                ton = time.replace(hour=6,minute=0)

            ton = ton.humanize(time, locale="de")
            description = "Online {}".format(ton)

        # start processing
        if self._camera_process.processing():
            self.loge("camera processing is still running")
            return False

        self._camera_process.process(self._video_online, description, time)
        return True


    def report_event(self):
        return dict(
            width=self._camera_process.get_image().size[0],
            height=self._camera_process.get_image().size[1],
            image=(
                self._online_file.get_read() if (
                    self._video_online
                ) else self._offline_file.get_read()
            ),
            video=self._video_file.get_read(),
            online=self._video_online
        )

    def shutdown_event(self):
        pygame.font.quit()
        pygame.camera.quit()
