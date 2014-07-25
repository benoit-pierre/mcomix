
from mcomix import image_tools
from mcomix import log

from collections import namedtuple

Rect = namedtuple('Rect', 'x y w h')
Frame = namedtuple('Frame', 'rect number split')

class SmartScroller(object):

    def __init__(self, debug=False):
        self._debug = debug
        self._max_imperfection_size = 3
        self._luminance_threshold = 16
        self._frames = []
        # First/last visible frames.
        self._current_frames = (0, 0)
        self._smart_scroll_possible = False
        self._image_width = 0
        self._image_height = 0
        self._view_x = 0
        self._view_y = 0
        self._view_width = 0
        self._view_height = 0

    def _is_bg_horz_line(self, x, y, w):
        count = 0
        for x in xrange(x, x + w):
            if 0 != self._pixels[x, y]:
                count = 0
            else:
                count += 1
                if count > self._max_imperfection_size:
                    return False
        return True

    def _is_bg_vert_line(self, x, y, h):
        count = 0
        for y in xrange(y, y + h):
            if 0 != self._pixels[x, y]:
                count = 0
            else:
                count += 1
                if count > self._max_imperfection_size:
                    return False
        return True

    def _crop(self, bbox):
        orig_bbox = bbox
        for y in xrange(bbox.h):
            y = bbox.y + y
            if not self._is_bg_horz_line(bbox.x, y, bbox.w):
                bbox = Rect(bbox.x, y, bbox.w, bbox.h - y + bbox.y)
                break
        for y in xrange(bbox.h):
            y = bbox.y + bbox.h - 1 - y
            if not self._is_bg_horz_line(bbox.x, y, bbox.w):
                bbox = Rect(bbox.x, bbox.y, bbox.w, y - bbox.y + 1)
                break
        for x in xrange(bbox.w):
            x = bbox.x + x
            if not self._is_bg_vert_line(x, bbox.y, bbox.h):
                bbox = Rect(x, bbox.y, bbox.w - x + bbox.x, bbox.h)
                break
        for x in xrange(bbox.w):
            x = bbox.x + bbox.w - 1 - x
            if not self._is_bg_vert_line(x, bbox.y, bbox.h):
                bbox = Rect(bbox.x, bbox.y, x - bbox.x + 1, bbox.h)
                break
        return bbox

    def _find_frames(self, bbox, split_horz=True, split_vert=True):
        orig_bbox = bbox
        bbox = self._crop(bbox)
        if bbox.w < self._min_frame_width or \
           bbox.h < self._min_frame_height:
            # Too small.
            return False
        if split_horz and bbox.h > self._min_frame_height * 2:
            was_bg_line = False
            for y in xrange(bbox.y + self._min_frame_height,
                            bbox.y + bbox.h - 2 * self._min_frame_height):
                is_bg_line = self._is_bg_horz_line(bbox.x, y, bbox.w)
                if is_bg_line == was_bg_line:
                    # Not a transition, ignore.
                    continue
                was_bg_line = is_bg_line
                if not is_bg_line:
                    # We found some content, ignore.
                    continue
                split = Rect(bbox.x, bbox.y, bbox.w, y - bbox.y)
                if not self._find_frames(split, split_horz=False):
                    continue
                split = Rect(bbox.x, y + 1, bbox.w, bbox.h - split.h - 1)
                if not self._find_frames(split):
                    continue
                return True
        if split_vert and bbox.w > self._min_frame_width * 2:
            was_bg_line = False
            for x in xrange(bbox.x + self._min_frame_width,
                            bbox.x + bbox.w - 2 * self._min_frame_width):
                is_bg_line = self._is_bg_vert_line(x, bbox.y, bbox.h)
                if is_bg_line == was_bg_line:
                    # Not a transition, ignore.
                    continue
                was_bg_line = is_bg_line
                if not is_bg_line:
                    # We found some content, ignore.
                    continue
                split = Rect(bbox.x, bbox.y, x - bbox.x, bbox.h)
                if not self._find_frames(split, split_vert=False):
                    continue
                split = Rect(x + 1, bbox.y, bbox.w - split.w - 1, bbox.h)
                if not self._find_frames(split):
                    continue
                return True
        self._frames.append(Frame(bbox, len(self._frames), None))
        return True

    def _is_rect_inside(self, rect, bbox):
        if rect.x < bbox.x:
            return False
        if rect.y < bbox.y:
            return False
        if rect.x + rect.w > bbox.x + bbox.w:
            return False
        if rect.y + rect.h > bbox.y + bbox.h:
            return False
        return True

    def _grow_bbox(self, bbox, rect):
        x = min(bbox.x, rect.x)
        y = min(bbox.y, rect.y)
        w = max(bbox.x + bbox.w, rect.x + rect.w)
        h = max(bbox.y + bbox.h, rect.y + rect.h)
        return Rect(x, y, w - x, h - y)

    def _split_frame(self, frame, max_width, max_height):
        if frame.rect.w <= max_width and frame.rect.h <= max_height:
            return (frame,)
        splits = []
        if frame.rect.h <= max_height:
            nb_horz_splits = 1
            split_height = frame.rect.h
        else:
            nb_horz_splits = (frame.rect.h + max_height - 1) / max_height
            split_height = frame.rect.h / nb_horz_splits
        if frame.rect.w <= max_width:
            nb_vert_splits = 1
            split_width = frame.rect.w
        else:
            nb_vert_splits = (frame.rect.w + max_width - 1) / max_width
            split_width = frame.rect.w / nb_vert_splits
        splits = []
        y = frame.rect.y
        for _ in range(nb_horz_splits):
            x = frame.rect.x
            for _ in range(nb_vert_splits):
                rect = Rect(x, y, split_width, split_height)
                splits.append(Frame(rect, frame.number, len(splits)))
                x += split_width
            y += split_height
        return splits

    def setup_image(self, pixbuf):

        if self._debug:
            self._debug_images = []

        bg = image_tools.get_most_common_edge_colour(pixbuf)
        bg = tuple([c * 255 / 65535 for c in bg[0:3]])
        bg_luminance = (bg[0] * 299 + bg[1] * 587 + bg[2] * 114) / 1000

        # Load image.
        im = image_tools.pixbuf_to_pil(pixbuf)
        if self._debug:
            self._debug_images.append(im)

        # Contert to grayscale.
        im = im.convert(mode='L')
        if self._debug:
            self._debug_images.append(im)

        # Convert to 2 tones: background, and the rest.
        table = []
        for n in xrange(256):
            if n < bg_luminance - self._luminance_threshold or \
               n > bg_luminance + self._luminance_threshold:
                n = 0
            else:
                n = 1
            table.append(n)
        im = im.point(table, mode='1')
        if self._debug:
            self._debug_images.append(im)

        self._image_width, self._image_height = im.size
        self._min_frame_width = max(64, self._image_width / 16)
        self._min_frame_height = max(64, self._image_height / 16)
        self._image = im
        self._pixels = im.load()

        bbox = Rect(0, 0, self._image_width, self._image_height)
        self._frames = []
        self._find_frames(bbox)
        if 0 == len(self._frames):
            self._frames = [Frame(bbox, 0, None)]
        self._current_frames = (0, 0)

        del self._pixels
        del self._image

    def setup_view(self, x, y, width, height):
        self._view_x = 0
        self._view_y = 0
        self._view_width = width
        self._view_height = height

        max_width = max(self._min_frame_width, width)
        max_height = max(self._min_frame_height, height)

        frames = []
        for f in self._frames:
            frames.extend(self._split_frame(f, max_width, max_height))
        self._frames = frames

    def _walk_frames_no_split(self, start, step):
        next_frame = last_frame = start
        while True:
            next_frame += step
            if next_frame < 0 or next_frame >= len(self._frames):
                return
            nf = self._frames[next_frame]
            lf = self._frames[last_frame]
            # Avoid spilling unto next frame if it's splitted.
            if nf.split is not None and nf.number != lf.number:
                return
            yield next_frame, nf

    def scroll(self, to_frame=None, backward=False):
        """ Scroll view, starting from <start>.
        <start> can be a frame number (e.g. 0 for first frame, -1 for last,
        ...) or a tuple (x, y) indicating the current viewport position.
        """

        if backward:
            step = -1
        else:
            step = +1

        if to_frame is not None:
            if to_frame >= 0:
                next_frame = to_frame
            else:
                next_frame = len(self._frames) + to_frame
            if next_frame < 0 or next_frame >= len(self._frames):
                log.error('Smart scrolling impossible: bad frame number: %u/%u', to_frame, len(self._frames))
                return None
        else:
            if backward:
                last_visible_frame = min(self._current_frames)
            else:
                last_visible_frame = max(self._current_frames)
            vbox = Rect(self._view_x, self._view_y, self._view_width, self._view_height)
            for n, f in self._walk_frames_no_split(last_visible_frame, step):
                if not self._is_rect_inside(f.rect, vbox):
                    break
                last_visible_frame = n
            next_frame = last_visible_frame + step
            if next_frame < 0 or next_frame >= len(self._frames):
                return None

        first_visible_frame = last_visible_frame = next_frame
        bbox = self._frames[next_frame].rect
        for n, f in self._walk_frames_no_split(first_visible_frame, step):
            new_bbox = self._grow_bbox(bbox, f.rect)
            if new_bbox.w > self._view_width or new_bbox.h > self._view_height:
                break
            last_visible_frame = n
            bbox = new_bbox

        self._current_frames = (first_visible_frame, last_visible_frame)

        left_width = self._view_width - bbox.w
        left_height = self._view_height - bbox.h

        x = bbox.x - left_width / 2
        y = bbox.y - left_height / 2

        if x < 0:
            x = 0
        elif self._image_width >= self._view_width and x + self._view_width > self._image_width:
            x = self._image_width - self._view_width
        if y < 0:
            y = 0
        elif self._image_height >= self._view_height and y + self._view_height > self._image_height:
            y = self._image_height - self._view_height

        self._view_x = x
        self._view_y = y

        return (self._view_x, self._view_y)

