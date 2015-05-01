"""lens.py - Magnifying lens."""

import math
import gtk

from mcomix.preferences import prefs
from mcomix import image_tools
from mcomix import constants


class MagnifyingLens(object):

    """The MagnifyingLens creates cursors from the raw pixbufs containing
    the unscaled data for the currently displayed images. It does this by
    looking at the cursor position and calculating what image data to put
    in the "lens" cursor.

    Note: The mapping is highly dependent on the exact layout of the main
    window images, thus this module isn't really independent from the main
    module as it uses implementation details not in the interface.
    """

    def __init__(self, window):
        self._window = window
        self._area = self._window._main_layout
        self._area.connect('motion-notify-event', self._motion_event)

        #: Stores lens state
        self._enabled = False
        #: Stores a tuple of the last mouse coordinates
        self._point = None
        #: Stores the last rectangle that was used to render the lens
        self._last_lens_rect = None

    def get_enabled(self):
        return self._enabled

    def set_enabled(self, enabled):
        self._enabled = enabled

        if enabled:
            # FIXME: If no file is currently loaded, the cursor will still be hidden.
            self._window.cursor_handler.set_cursor_type(constants.NO_CURSOR)
            self._window.osd.clear()

            if self._point:
                self._draw_lens(*self._point)
        else:
            self._window.cursor_handler.set_cursor_type(constants.NORMAL_CURSOR)
            self._clear_lens()
            self._last_lens_rect = None

    enabled = property(get_enabled, set_enabled)

    def _draw_lens(self, x, y):
        """Calculate what image data to put in the lens and update the cursor
        with it; <x> and <y> are the positions of the cursor within the
        main window layout area.
        """
        if not self._window.filehandler.file_loaded or not self._window.images[0].get_pixbuf(): # XXX transitional(double page limitation)
            return

        rectangle = self._calculate_lens_rect(x, y, prefs['lens size'], prefs['lens size'])
        pixbuf = self._get_lens_pixbuf(x, y)

        # Region used to draw the pixbuf
        lens_region = gtk.gdk.region_rectangle(rectangle)
        # Combined regions (area that will be drawn to in this operation
        full_region = lens_region.copy()
        if self._last_lens_rect:
            last_region = gtk.gdk.region_rectangle(self._last_lens_rect)
            full_region.union(last_region)

        window = self._area.get_bin_window()
        window.begin_paint_region(full_region)
        self._clear_lens(lens_region)
        window.draw_pixbuf(None, pixbuf, 0, 0, *rectangle)
        window.end_paint()

        self._last_lens_rect = rectangle

    def _calculate_lens_rect(self, x, y, width, height):
        """ Calculates the area where the lens will be drawn on screen. This method takes
        screen space into calculation and moves the rectangle accordingly when the the rectangle
        would otherwise flow over the allocated area. """

        lens_x = max(x - width // 2, 0)
        lens_y = max(y - height // 2, 0)

        max_width, max_height = self._window.get_visible_area_size()
        max_width += int(self._window._hadjust.get_value())
        max_height += int(self._window._vadjust.get_value())
        lens_x = min(lens_x, max_width - width)
        lens_y = min(lens_y, max_height - height)

        # Don't forget 1 pixel border...
        return lens_x, lens_y, width + 2, height + 2

    def _clear_lens(self, current_lens_region=None):
        """ Invalidates the area that was damaged by the last call to draw_lens.
        If <current_lens_region> is not None, this region will not be invalidated. """

        if not self._last_lens_rect:
            return

        last_region = gtk.gdk.region_rectangle(self._last_lens_rect)
        if current_lens_region:
            last_region.subtract(current_lens_region)

        self._area.get_bin_window().invalidate_region(last_region, True)

    def toggle(self, action):
        """Toggle on or off the lens depending on the state of <action>."""
        self.enabled = action.get_active()

    def _motion_event(self, widget, event):
        """ Called whenever the mouse moves over the image area. """
        self._point = (int(event.x), int(event.y))
        if self.enabled:
            self._draw_lens(*self._point)

    def _get_lens_pixbuf(self, x, y):
        """Get a pixbuf containing the appropiate image data for the lens
        where <x> and <y> are the positions of the cursor.
        """
        canvas = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8,
            prefs['lens size'], prefs['lens size'])
        canvas.fill(image_tools.convert_rgb16list_to_rgba8int(self._window.get_bg_colour()))
        cb = self._window.layout.get_content_boxes()
        source_pixbufs = self._window.imagehandler.get_pixbufs(len(cb))
        for i in range(len(cb)):
            cpos = cb[i].get_position()
            self._add_subpixbuf(canvas, x - cpos[0], y - cpos[1],
                cb[i].get_size(), source_pixbufs[i])

        return image_tools.add_border(canvas, 1)

    def _add_subpixbuf(self, canvas, x, y, image_size, source_pixbuf):
        """Copy a subpixbuf from <source_pixbuf> to <canvas> as it should
        be in the lens if the coordinates <x>, <y> are the mouse pointer
        position on the main window layout area.

        The displayed image (scaled from the <source_pixbuf>) must have
        size <image_size>.
        """
        # Prevent division by zero exceptions further down
        if not image_size[0]:
            return

        rotation = prefs['rotation']
        if prefs['auto rotate from exif']:
            rotation += image_tools.get_implied_rotation(source_pixbuf)
            rotation = rotation % 360

        if rotation in [90, 270]:
            scale = float(source_pixbuf.get_height()) / image_size[0]
        else:
            scale = float(source_pixbuf.get_width()) / image_size[0]

        x *= scale
        y *= scale

        source_mag = prefs['lens magnification'] / scale
        width = height = prefs['lens size'] / source_mag

        paste_left = x > width / 2
        paste_top = y > height / 2
        dest_x = max(0, int(math.ceil((width / 2 - x) * source_mag)))
        dest_y = max(0, int(math.ceil((height / 2 - y) * source_mag)))

        if rotation == 90:
            x, y = y, source_pixbuf.get_height() - x
        elif rotation == 180:
            x = source_pixbuf.get_width() - x
            y = source_pixbuf.get_height() - y
        elif rotation == 270:
            x, y = source_pixbuf.get_width() - y, x
        if prefs['horizontal flip']:
            if rotation in (90, 270):
                y = source_pixbuf.get_height() - y
            else:
                x = source_pixbuf.get_width() - x
        if prefs['vertical flip']:
            if rotation in (90, 270):
                x = source_pixbuf.get_width() - x
            else:
                y = source_pixbuf.get_height() - y

        src_x = x - width / 2
        src_y = y - height / 2
        if src_x < 0:
            width += src_x
            src_x = 0
        if src_y < 0:
            height += src_y
            src_y = 0
        width = max(0, min(source_pixbuf.get_width() - src_x, width))
        height = max(0, min(source_pixbuf.get_height() - src_y, height))
        if width < 1 or height < 1:
            return

        subpixbuf = source_pixbuf.subpixbuf(int(src_x), int(src_y),
            int(width), int(height))
        subpixbuf = subpixbuf.scale_simple(
            int(math.ceil(source_mag * subpixbuf.get_width())),
            int(math.ceil(source_mag * subpixbuf.get_height())),
            prefs['scaling quality'])

        if rotation == 90:
            subpixbuf = subpixbuf.rotate_simple(
                gtk.gdk.PIXBUF_ROTATE_CLOCKWISE)
        elif rotation == 180:
            subpixbuf = subpixbuf.rotate_simple(
                gtk.gdk.PIXBUF_ROTATE_UPSIDEDOWN)
        elif rotation == 270:
            subpixbuf = subpixbuf.rotate_simple(
                gtk.gdk.PIXBUF_ROTATE_COUNTERCLOCKWISE)
        if prefs['horizontal flip']:
            subpixbuf = subpixbuf.flip(horizontal=True)
        if prefs['vertical flip']:
            subpixbuf = subpixbuf.flip(horizontal=False)

        subpixbuf = self._window.enhancer.enhance(subpixbuf)

        if paste_left:
            dest_x = 0
        else:
            dest_x = min(canvas.get_width() - subpixbuf.get_width(), dest_x)
        if paste_top:
            dest_y = 0
        else:
            dest_y = min(canvas.get_height() - subpixbuf.get_height(), dest_y)

        if subpixbuf.get_has_alpha() and prefs['checkered bg for transparent images']:
            subpixbuf = subpixbuf.composite_color_simple(subpixbuf.get_width(), subpixbuf.get_height(),
                gtk.gdk.INTERP_NEAREST, 255, 8, 0x777777, 0x999999)

        subpixbuf.copy_area(0, 0, subpixbuf.get_width(),
            subpixbuf.get_height(), canvas, dest_x, dest_y)

# vim: expandtab:sw=4:ts=4
