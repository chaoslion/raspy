# -*- coding: utf-8 -*-
from PIL import Image, ImageFilter

class Skydetector(object):

    def __init__(self, size):
        self._image = Image.new("RGB", size)

    def get_image(self):
        return self._image

    # def _is_skypixel_algo1(self, pixel):
    #     r = pixel[0]
    #     g = pixel[1]
    #     b = pixel[2]

    #     rg =  r - g
    #     if rg < 0:
    #         rg = 0

    #     gb = g - b
    #     if gb < 0:
    #         gb = 0

    #     return (
    #         (rg < 5) and (gb < 5) and
    #         (b > r) and (b > g) and
    #         (b > 50) and (b < 230)
    #     )

    # def _count_skypixel(self, img):
    #     cnt = 0
    #     pixels = list(img.getdata())
    #     for p in pixels:
    #         if self._is_skypixel_algo1(p):
    #             cnt += 1
    #     return cnt

    # turn all non sky pixels black
    def detect(self, img, blur_area):

        self._image = img.copy()
        # self._image.paste(img, (0,0) + img.size)

        # turn all non sky pixel into sky
        cols = dict()
        mask = [False for _ in range(self._image.size[0])]
        pixels = self._image.load()
        for y in range(self._image.size[1]):
            cols.clear()

            # first pass
            for x in range(self._image.size[0]):
                r, g, b = pixels[x,y]
                if (r >= 51 and g >= 94 and b >= 127):
                    rgb = r << 16 | g << 8 | b

                    if rgb in cols:
                        cols[rgb] += 1
                    else:
                        cols[rgb] = 0
                else:
                    mask[x] = True

            # is empty? -> skip 2nd pass
            if not cols:
                continue

            # get max color
            max_blue = max(cols, key=cols.get)
            r = (max_blue & 0xFF0000) >> 16
            g = (max_blue & 0x00FF00) >> 8
            b = (max_blue & 0x0000FF)

            # second pass
            for x in range(self._image.size[0]):
                if mask[x]:
                    pixels[x,y] = (r, g, b)
                mask[x] = False

        # blur house
        self._image.paste(
            self._image.crop(blur_area).filter(ImageFilter.GaussianBlur(radius=4)),
            blur_area
        )
