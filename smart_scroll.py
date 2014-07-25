#!/usr/bin/env python2

from mcomix import image_tools
from mcomix.smart_scroller import Rect, SmartScroller

from PIL import ImageColor, ImageFont, ImageDraw

import pygtk
pygtk.require('2.0')

import traceback
import pdb
import gtk
import sys
import os


class Scroller(object):

    def __init__(self, pages, getkey):

        self.getkey = getkey
        self.current_page = 0
        self.pages = pages
        self.debug = False
        self.line_width = 3
        self.font = ImageFont.truetype("/usr/share/fonts/TTF/arial.ttf", 20)
        if self.font is None:
            self.font = ImageFont.load_default()
        self.zoom_levels = (
            (640, 480),
            (800, 600),
            (1024, 768),
            (1920, 1200),
            (1920 * 2, 1200 * 2),
            (4000, 1200 * 2),
        )
        self.current_zoom = 1
        self.scroller = SmartScroller(debug=self.debug)

    def draw_rect(self, draw, rect, color):
        draw_color = ImageColor.getrgb(color)
        tlx, tly = rect.x, rect.y
        brx, bry = rect.x + rect.w - 1, rect.y + rect.h - 1
        draw.line((tlx, tly,
                   brx, tly,
                   brx, bry,
                   tlx, bry,
                   tlx, tly), fill=draw_color, width=self.line_width)
        draw.line((tlx, tly,
                   brx, bry), fill=draw_color, width=self.line_width)
        draw.line((tlx, bry,
                   brx, tly), fill=draw_color, width=self.line_width)

    def highlight_frames(self, im, frames, frames_color, bbox=None,
                         bbox_color=None, numbering=False):
        im = im.copy()
        draw = ImageDraw.Draw(im)
        if bbox is not None:
            self.draw_rect(draw, bbox, bbox_color)
        if numbering:
            text_color = ImageColor.getrgb(numbering)
        for f in frames:
            self.draw_rect(draw, f.rect, frames_color)
            if numbering:
                text = str(f.number)
                if f.split is not None:
                    text += '.%s' % str(f.split)
                w, h = self.font.getsize(text)
                x, y = f.rect.x, f.rect.y + f.rect.h - 2 * h
                draw.rectangle((x - w / 2, y - h / 2, x + 2 * w, y + 2 * h), fill=0)
                draw.text((x, y), text, font=self.font, fill=text_color)
        del draw
        return im

    def update_page(self):

        print 'loading page %u' % self.current_page

        self.view_width, self.view_height = self.zoom_levels[self.current_zoom]

        pixbuf = image_tools.load_pixbuf(self.pages[self.current_page])

        self.scroller.setup_image(pixbuf)

        print 'page size: %ux%u' % (self.scroller._image_width,
                                    self.scroller._image_height)
        print 'minimum frame size: %ux%u' % (self.scroller._min_frame_width,
                                             self.scroller._min_frame_height)

        self.scroller.setup_view(0, 0, self.view_width, self.view_height)
        self.x, self.y = 0, 0

        if self.debug:
            for im in self.scroller._debug_images:
                yield im
                self.getkey()

        im = image_tools.pixbuf_to_pil(pixbuf)
        self.image = self.highlight_frames(im, self.scroller._frames, 'red', numbering='orange')

    def main_loop(self):

        for im in self.update_page():
            yield im

        to_frame = 0
        backward = False
        while True:
            msg = 'scrolling '
            if backward:
                msg += 'up'
            else:
                msg += 'down'
            if to_frame is None:
                msg += ' from frames %s' % str(self.scroller._current_frames)
            else:
                msg += ' to frame %u' % to_frame
            print msg

            position = self.scroller.scroll(to_frame=to_frame, backward=backward)
            to_frame = None
            if position is None:
                if backward:
                    step = -1
                    to_frame = -1
                else:
                    step = +1
                    to_frame = 0
                self.current_page = self.current_page + step + len(self.pages)
                self.current_page %= len(self.pages)
                for im in self.update_page():
                    yield im
                continue

            msg = 'scrolling to %s' % str(position)
            msg += ', frames %s' % str(self.scroller._current_frames)
            print msg

            self.x, self.y = position
            vbox = Rect(self.x, self.y, self.view_width, self.view_height)
            im = self.highlight_frames(self.image, (), None, vbox, 'blue')
            yield im

            while True:

                k = self.getkey()
                if k is None:
                    yield
                    continue

                if 'd' == k:
                    self.debug = not self.debug
                    self.scroller._debug = self.debug
                    if self.debug:
                        k = 'r'

                if 'r' == k:
                    for im in self.update_page():
                        yield im
                    backward = False
                    to_frame = 0
                    break

                if k in '0123456789':
                    num = k
                    while True:
                        yield None
                        k = self.getkey()
                        if not k in '0123456789':
                            break
                        num += k
                    num = int(num)
                    if 'f' == k:
                        to_frame = num
                    elif 'p' == k:
                        nb_pages = len(self.pages)
                        self.current_page = (num + nb_pages - 1) % nb_pages
                        for im in self.update_page():
                            yield im
                        backward = False
                        to_frame = 0
                    break

                if k in ('minus', 'plus', 'equal'):
                    if 'minus' == k:
                        step = -1
                    else:
                        step = +1
                    self.current_zoom += step + len(self.zoom_levels)
                    self.current_zoom %= len(self.zoom_levels)
                    for im in self.update_page():
                        yield im
                    to_frame = max(*self.scroller._current_frames)
                    break

                if k in ('Up', 'BackSpace', 'e'):
                    backward = True
                    break

                if k in ('Down', 'space', 'n'):
                    backward = False
                    break

                if k in ('Left', 'Right'):
                    if 'Left' == k:
                        step = -1
                    else:
                        step = +1
                    to_frame = 0
                    self.current_page = self.current_page + step + len(self.pages)
                    self.current_page %= len(self.pages)
                    for im in self.update_page():
                        yield im
                    break

                yield


class TestScroller():

    def __init__(self, pages):

        self.scroller = Scroller(pages, self.getkey)
        self.scroller_generator = self.scroller.main_loop()

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect('key_release_event', self.on_key_release)
        self.window.connect('destroy', self.on_destroy)
        self.window.set_title('mcomix-test-scroller')
        self.window.set_default_size(780, 1100)

        self.viewport = gtk.ScrolledWindow()
        self.viewport.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.viewport.set_border_width(0)
        self.window.add(self.viewport)

        self.image = gtk.Image()
        self.update_image()
        self.viewport.add_with_viewport(self.image)

        self.image.show()
        self.viewport.show()
        self.window.show()

    def update_image(self):
        im = self.scroller_generator.next()
        if im is None:
            return
        pixbuf = image_tools.pil_to_pixbuf(im)
        self.image.set_from_pixbuf(pixbuf)
        self.viewport.get_hadjustment().set_value(self.scroller.x)
        self.viewport.get_vadjustment().set_value(self.scroller.y)

    def getkey(self):
        return self.key

    def on_destroy(self, widget, data=None):
        gtk.main_quit()

    def on_key_release(self, widget, data=None):
        self.key = gtk.gdk.keyval_name(data.keyval)
        if self.key in ('Escape', 'q'):
            gtk.main_quit()
        self.update_image()
        return True

    def main(self):
        gtk.main()


try:
    ts = TestScroller(sys.argv[1:])
    ts.main()
except Exception:
    print traceback.format_exc()
    pdb.post_mortem()

