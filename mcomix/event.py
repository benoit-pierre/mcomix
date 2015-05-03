"""event.py - Event handling (keyboard, mouse, etc.) for the main window.
"""

import urllib
import gtk

from mcomix.preferences import prefs
from mcomix import constants
from mcomix import portability
from mcomix import keybindings
from mcomix import openwith


class EventHandler(object):

    def __init__(self, window):
        self._window = window

        self._last_pointer_pos_x = 0
        self._last_pointer_pos_y = 0
        self._pressed_pointer_pos_x = 0
        self._pressed_pointer_pos_y = 0

        #: For scrolling "off the page".
        self._extra_scroll_events = 0
        #: If True, increment _extra_scroll_events before switchting pages
        self._scroll_protection = False

    def resize_event(self, widget, event):
        """Handle events from resizing and moving the main window."""
        size = (event.width, event.height)
        if size != self._window.previous_size:
            self._window.previous_size = size
            self._window.draw_image()

    def window_state_event(self, widget, event):
        is_fullscreen = self._window.is_fullscreen
        if self._window.was_fullscreen != is_fullscreen:
            # Fullscreen state changed.
            self._window.was_fullscreen = is_fullscreen
            # Re-enable control, now that transition is complete.
            toggleaction = self._window.actiongroup.get_action('fullscreen')
            toggleaction.set_sensitive(True)
            if is_fullscreen:
                redraw = True
            else:
                # Only redraw if we don't need to restore geometry.
                redraw = not self._window.restore_window_geometry()
            self._window._update_toggles_sensitivity()
            if redraw:
                self._window.previous_size = self._window.get_size()
                self._window.draw_image()

    def register_key_events(self):
        """ Registers keyboard events and their default binings, and hooks
        them up with their respective callback functions. """

        manager = keybindings.keybinding_manager(self._window)

        # Navigation keys
        manager.register('previous_page',
            ['Page_Up', 'KP_Page_Up', 'BackSpace'],
            self._flip_page, kwargs={'number_of_pages': -1})
        manager.register('next_page',
            ['Page_Down', 'KP_Page_Down'],
            self._flip_page, kwargs={'number_of_pages': 1})
        manager.register('previous_page_singlestep',
            ['<Ctrl>Page_Up', '<Ctrl>KP_Page_Up', '<Ctrl>BackSpace'],
            self._flip_page, kwargs={'number_of_pages': -1, 'single_step': True})
        manager.register('next_page_singlestep',
            ['<Ctrl>Page_Down', '<Ctrl>KP_Page_Down'],
            self._flip_page, kwargs={'number_of_pages': 1, 'single_step': True})
        manager.register('previous_page_dynamic',
            ['<Mod1>Left'],
            self._left_right_page_progress, kwargs={'number_of_pages': -1})
        manager.register('next_page_dynamic',
            ['<Mod1>Right'],
            self._left_right_page_progress, kwargs={'number_of_pages': 1})

        manager.register('previous_page_ff',
            ['<Shift>Page_Up', '<Shift>KP_Page_Up', '<Shift>BackSpace', '<Shift><Mod1>Left'],
            self._flip_page, kwargs={'number_of_pages': -10})
        manager.register('next_page_ff',
            ['<Shift>Page_Down', '<Shift>KP_Page_Down', '<Shift><Mod1>Right'],
            self._flip_page, kwargs={'number_of_pages': 10})


        manager.register('first_page',
            ['Home', 'KP_Home'],
            self._window.first_page)
        manager.register('last_page',
            ['End', 'KP_End'],
            self._window.last_page)
        manager.register('go_to',
            ['G'],
            self._window.page_select)

        # Numpad (without numlock) aligns the image depending on the key.
        manager.register('scroll_left_bottom',
            ['KP_1'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (-1, 1), 'index': constants.UNION_INDEX})
        manager.register('scroll_middle_bottom',
            ['KP_2'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (constants.SCROLL_TO_CENTER, 1),
                'index': constants.UNION_INDEX})
        manager.register('scroll_right_bottom',
            ['KP_3'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (1, 1), 'index': constants.UNION_INDEX})

        manager.register('scroll_left_middle',
            ['KP_4'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (-1, constants.SCROLL_TO_CENTER),
                'index': constants.UNION_INDEX})
        manager.register('scroll_middle',
            ['KP_5'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (constants.SCROLL_TO_CENTER,
                constants.SCROLL_TO_CENTER), 'index': constants.UNION_INDEX})
        manager.register('scroll_right_middle',
            ['KP_6'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (1, constants.SCROLL_TO_CENTER),
                'index': constants.UNION_INDEX})

        manager.register('scroll_left_top',
            ['KP_7'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (-1, -1), 'index': constants.UNION_INDEX})
        manager.register('scroll_middle_top',
            ['KP_8'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (constants.SCROLL_TO_CENTER, -1),
                'index': constants.UNION_INDEX})
        manager.register('scroll_right_top',
            ['KP_9'],
            self._window.scroll_to_predefined,
            kwargs={'destination': (1, -1), 'index': constants.UNION_INDEX})

        # Enter/exit fullscreen.
        manager.register('exit_fullscreen',
            ['Escape'],
            self.escape_event)

        # View modes
        manager.register('double_page',
            ['d'],
            self._window.actiongroup.get_action('double_page').activate)


        manager.register('best_fit_mode',
            ['b'],
            self._window.actiongroup.get_action('best_fit_mode').activate)

        manager.register('fit_width_mode',
            ['w'],
            self._window.actiongroup.get_action('fit_width_mode').activate)

        manager.register('fit_height_mode',
            ['h'],
            self._window.actiongroup.get_action('fit_height_mode').activate)

        manager.register('fit_size_mode',
            ['s'],
            self._window.actiongroup.get_action('fit_size_mode').activate)

        manager.register('fit_manual_mode',
            ['a'],
            self._window.actiongroup.get_action('fit_manual_mode').activate)


        manager.register('manga_mode',
            ['m'],
            self._window.actiongroup.get_action('manga_mode').activate)

        manager.register('invert_scroll',
            ['x'],
            self._window.actiongroup.get_action('invert_scroll').activate)

        manager.register('keep_transformation',
            ['k'],
            self._window.actiongroup.get_action('keep_transformation').activate)

        manager.register('lens',
            ['l'],
            self._window.actiongroup.get_action('lens').activate)

        manager.register('stretch',
            ['y'],
            self._window.actiongroup.get_action('stretch').activate)

        # Zooming commands for manual zoom mode
        manager.register('zoom_in',
            ['plus', 'KP_Add', 'equal'],
            self._window.actiongroup.get_action('zoom_in').activate)
        manager.register('zoom_out',
            ['minus', 'KP_Subtract'],
            self._window.actiongroup.get_action('zoom_out').activate)
        # Zoom out is already defined as GTK menu hotkey
        manager.register('zoom_original',
            ['<Control>0', 'KP_0'],
            self._window.actiongroup.get_action('zoom_original').activate)

        manager.register('rotate_90',
            ['r'],
            self._window.rotate_90)

        manager.register('rotate_270',
            ['<Shift>r'],
            self._window.rotate_270)

        manager.register('rotate_180',
            [],
            self._window.rotate_180)

        manager.register('flip_horiz',
            [],
            self._window.flip_horizontally)

        manager.register('flip_vert',
            [],
            self._window.flip_vertically)

        manager.register('no_autorotation',
            [],
            self._window.actiongroup.get_action('no_autorotation').activate)

        manager.register('rotate_90_width',
            [],
            self._window.actiongroup.get_action('rotate_90_width').activate)
        manager.register('rotate_270_width',
            [],
            self._window.actiongroup.get_action('rotate_270_width').activate)

        manager.register('rotate_90_height',
            [],
            self._window.actiongroup.get_action('rotate_90_height').activate)

        manager.register('rotate_270_height',
            [],
            self._window.actiongroup.get_action('rotate_270_height').activate)

        # Arrow keys scroll the image
        manager.register('scroll_down',
            ['Down', 'KP_Down'],
            self._scroll_down)
        manager.register('scroll_up',
            ['Up', 'KP_Up'],
            self._scroll_up)
        manager.register('scroll_right',
            ['Right', 'KP_Right'],
            self._scroll_right)
        manager.register('scroll_left',
            ['Left', 'KP_Left'],
            self._scroll_left)

        # File operations
        manager.register('close',
            ['<Control>W'],
            self._window.filehandler.close_file)

        manager.register('quit',
            ['<Control>Q'],
            self._window.close_program)

        manager.register('save_and_quit',
            ['<Control><shift>q'],
            self._window.save_and_terminate_program)

        manager.register('delete',
            ['Delete'],
            self._window.delete)

        manager.register('extract_page',
            ['<Control><Shift>s'],
            self._window.extract_page)

        manager.register('refresh_archive',
            ['<control><shift>R'],
            self._window.filehandler.refresh_file)

        manager.register('next_archive',
            ['<control><shift>N'],
            self._window.filehandler._open_next_archive)

        manager.register('previous_archive',
            ['<control><shift>P'],
            self._window.filehandler._open_previous_archive)

        manager.register('next_directory',
            ['<control>N'],
            self._window.filehandler.open_next_directory)

        manager.register('previous_directory',
            ['<control>P'],
            self._window.filehandler.open_previous_directory)

        manager.register('comments',
            ['c'],
            self._window.actiongroup.get_action('comments').activate)

        manager.register('properties',
            ['<Alt>Return'],
            self._window.actiongroup.get_action('properties').activate)

        manager.register('preferences',
            ['F12'],
            self._window.actiongroup.get_action('preferences').activate)

        manager.register('edit_archive',
            [],
            self._window.actiongroup.get_action('edit_archive').activate)

        manager.register('open',
            ['<Control>O'],
            self._window.actiongroup.get_action('open').activate)

        manager.register('enhance_image',
            ['e'],
            self._window.actiongroup.get_action('enhance_image').activate)

        manager.register('library',
            ['<Control>L'],
            self._window.actiongroup.get_action('library').activate)

        # Space key scrolls down a percentage of the window height or the
        # image height at a time. When at the bottom it flips to the next
        # page.
        #
        # It also has a "smart scrolling mode" in which we try to follow
        # the flow of the comic.
        #
        # If Shift is pressed we should backtrack instead.
        manager.register('smart_scroll_down',
            ['space'],
            self._smart_scroll_down)
        manager.register('smart_scroll_up',
            ['<Shift>space'],
            self._smart_scroll_up)

        # User interface
        manager.register('osd_panel',
            ['Tab'],
            self._window.show_info_panel)

        manager.register('minimize',
            ['n'],
            self._window.minimize)

        manager.register('fullscreen',
            ['f', 'F11'],
            self._window.actiongroup.get_action('fullscreen').activate)

        manager.register('toolbar',
            [],
            self._window.actiongroup.get_action('toolbar').activate)

        manager.register('menubar',
            ['<Control>M'],
            self._window.actiongroup.get_action('menubar').activate)

        manager.register('statusbar',
            [],
            self._window.actiongroup.get_action('statusbar').activate)

        manager.register('scrollbar',
            [],
            self._window.actiongroup.get_action('scrollbar').activate)

        manager.register('thumbnails',
            ['F9'],
            self._window.actiongroup.get_action('thumbnails').activate)


        manager.register('hide_all',
            ['i'],
            self._window.actiongroup.get_action('hide_all').activate)

        manager.register('slideshow',
            ['<Control>S'],
            self._window.actiongroup.get_action('slideshow').activate)

        # Execute external command. Bind keys from 1 to 9 to commands 1 to 9.
        for i in range(1, 10):
            manager.register('execute_command_%d' % i, ['%d' % i],
                             self._execute_command, args=[i - 1])

    def key_press_event(self, widget, event, *args):
        """Handle key press events on the main window."""

        # This is set on demand by callback functions
        self._scroll_protection = False

        # Dispatch keyboard input handling
        manager = keybindings.keybinding_manager(self._window)
        # Some keys can only be pressed with certain modifiers that
        # are irrelevant to the actual hotkey. Find out and ignore them.
        ALL_ACCELS_MASK = (gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK |
                           gtk.gdk.MOD1_MASK)

        keymap = gtk.gdk.keymap_get_default()
        code = keymap.translate_keyboard_state(
                event.hardware_keycode, event.state, event.group)

        if code is not None:
            keyval, egroup, level, consumed = code

            # If the resulting key is upper case (i.e. SHIFT + key),
            # convert it to lower case and remove SHIFT from the consumed flags
            # to match how keys are registered (<Shift> + lowercase)
            if (gtk.gdk.keyval_is_upper(keyval) and
                not gtk.gdk.keyval_is_lower(keyval) and
                event.state & gtk.gdk.SHIFT_MASK):
                keyval = gtk.gdk.keyval_to_lower(keyval)
                consumed &= ~gtk.gdk.SHIFT_MASK

            # 'consumed' is the modifier that was necessary to type the key
            manager.execute((keyval, event.state & ~consumed & ALL_ACCELS_MASK))

        # ---------------------------------------------------------------
        # Register CTRL for scrolling only one page instead of two
        # pages in double page mode. This is mainly for mouse scrolling.
        # ---------------------------------------------------------------
        if event.keyval in (gtk.keysyms.Control_L, gtk.keysyms.Control_R):
            self._window.imagehandler.force_single_step = True

        # ----------------------------------------------------------------
        # We kill the signals here for the Up, Down, Space and Enter keys,
        # or they will start fiddling with the thumbnail selector (bad).
        # ----------------------------------------------------------------
        if (event.keyval in (gtk.keysyms.Up, gtk.keysyms.Down,
          gtk.keysyms.space, gtk.keysyms.KP_Enter, gtk.keysyms.KP_Up,
          gtk.keysyms.KP_Down, gtk.keysyms.KP_Home, gtk.keysyms.KP_End,
          gtk.keysyms.KP_Page_Up, gtk.keysyms.KP_Page_Down) or
          (event.keyval == gtk.keysyms.Return and not
          'GDK_MOD1_MASK' in event.state.value_names)):

            self._window.emit_stop_by_name('key_press_event')
            return True

    def key_release_event(self, widget, event, *args):
        """ Handle release of keys for the main window. """

        # ---------------------------------------------------------------
        # Unregister CTRL for scrolling only one page in double page mode
        # ---------------------------------------------------------------
        if event.keyval in (gtk.keysyms.Control_L, gtk.keysyms.Control_R):
            self._window.imagehandler.force_single_step = False

    def escape_event(self):
        """ Determines the behavior of the ESC key. """
        if prefs['escape quits']:
            self._window.close_program()
        else:
            self._window.actiongroup.get_action('fullscreen').set_active(False)

    def scroll_wheel_event(self, widget, event, *args):
        """Handle scroll wheel events on the main layout area. The scroll
        wheel flips pages in best fit mode and scrolls the scrollbars
        otherwise.
        """
        if 'GDK_BUTTON2_MASK' in event.state.value_names:
            return

        self._scroll_protection = True

        if event.direction == gtk.gdk.SCROLL_UP:
            if event.state & gtk.gdk.CONTROL_MASK:
                self._window.manual_zoom_in()
            elif prefs['smart scroll']:
                self._smart_scroll_up(prefs['number of pixels to scroll per mouse wheel event'])
            else:
                self._scroll_with_flipping(0, -prefs['number of pixels to scroll per mouse wheel event'])

        elif event.direction == gtk.gdk.SCROLL_DOWN:
            if event.state & gtk.gdk.CONTROL_MASK:
                self._window.manual_zoom_out()
            elif prefs['smart scroll']:
                self._smart_scroll_down(prefs['number of pixels to scroll per mouse wheel event'])
            else:
                self._scroll_with_flipping(0, prefs['number of pixels to scroll per mouse wheel event'])

        elif event.direction == gtk.gdk.SCROLL_RIGHT:
            if not self._window.is_manga_mode:
                self._window.flip_page(+1)
            else:
                self._previous_page_with_protection()

        elif event.direction == gtk.gdk.SCROLL_LEFT:
            if not self._window.is_manga_mode:
                self._previous_page_with_protection()
            else:
                self._window.flip_page(+1)

    def mouse_press_event(self, widget, event):
        """Handle mouse click events on the main layout area."""

        if self._window.was_out_of_focus:
            return

        if event.button == 1:
            self._pressed_pointer_pos_x = event.x_root
            self._pressed_pointer_pos_y = event.y_root
            self._last_pointer_pos_x = event.x_root
            self._last_pointer_pos_y = event.y_root

        elif event.button == 2:
            self._window.actiongroup.get_action('lens').set_active(True)

        elif (event.button == 3 and
              not event.state & gtk.gdk.MOD1_MASK and
              not event.state & gtk.gdk.SHIFT_MASK):
            self._window.cursor_handler.set_cursor_type(constants.NORMAL_CURSOR)
            self._window.popup.popup(None, None, None, event.button,
                event.time)

        elif event.button == 4:
            self._window.show_info_panel()

    def mouse_release_event(self, widget, event):
        """Handle mouse button release events on the main layout area."""

        self._window.cursor_handler.set_cursor_type(constants.NORMAL_CURSOR)

        if (event.button == 1):

            if event.x_root == self._pressed_pointer_pos_x and \
                event.y_root == self._pressed_pointer_pos_y and \
                not self._window.was_out_of_focus:

                if event.state & gtk.gdk.SHIFT_MASK:
                    self._flip_page(10)
                else:
                    self._flip_page(1)

            else:
                self._window.was_out_of_focus = False

        elif event.button == 2:
            self._window.actiongroup.get_action('lens').set_active(False)

        elif event.button == 3:
            if event.state & gtk.gdk.MOD1_MASK:
                self._flip_page(-1)
            elif event.state & gtk.gdk.SHIFT_MASK:
                self._flip_page(-10)

    def mouse_move_event(self, widget, event):
        """Handle mouse pointer movement events."""

        event = _get_latest_event_of_same_type(event)

        if 'GDK_BUTTON1_MASK' in event.state.value_names:
            self._window.cursor_handler.set_cursor_type(constants.GRAB_CURSOR)
            scrolled = self._window.scroll(self._last_pointer_pos_x - event.x_root,
                                           self._last_pointer_pos_y - event.y_root)

            # Cursor wrapping stuff. See:
            # https://sourceforge.net/tracker/?func=detail&aid=2988441&group_id=146377&atid=764987
            if prefs['wrap mouse scroll'] and scrolled:
                # FIXME: Problems with multi-screen setups
                screen = self._window.get_screen()
                warp_x0 = warp_y0 = 0
                warp_x1 = screen.get_width()
                warp_y1 = screen.get_height()

                new_x = _valwarp(event.x_root, warp_x1, minval=warp_x0)
                new_y = _valwarp(event.y_root, warp_y1, minval=warp_y0)
                if (new_x != event.x_root) or (new_y != event.y_root):
                    display = screen.get_display()
                    display.warp_pointer(screen, int(new_x), int(new_y))
                    ## This might be (or might not be) necessary to avoid
                    ## doing one warp multiple times.
                    event = _get_latest_event_of_same_type(event)

                self._last_pointer_pos_x = new_x
                self._last_pointer_pos_y = new_y
            else:
                self._last_pointer_pos_x = event.x_root
                self._last_pointer_pos_y = event.y_root
            self._drag_timer = event.time

    def drag_n_drop_event(self, widget, context, x, y, selection, drag_id,
      eventtime):
        """Handle drag-n-drop events on the main layout area."""
        # The drag source is inside MComix itself, so we ignore.

        if (context.get_source_widget() is not None):
            return

        uris = selection.get_uris()

        if not uris:
            return

        # Normalize URIs
        uris = [portability.normalize_uri(uri) for uri in uris]
        paths = [urllib.url2pathname(uri).decode('utf-8') for uri in uris]

        if len(paths) > 1:
            self._window.filehandler.open_file(paths)
        else:
            self._window.filehandler.open_file(paths[0])

    def _scroll_with_flipping(self, x, y):
        """Handle scrolling with the scroll wheel or the arrow keys, for which
        the pages might be flipped depending on the preferences.  Returns True
        if able to scroll without flipping and False if a new page was flipped
        to.
        """

        self._scroll_protection = True

        if self._window.scroll(x, y):
            self._extra_scroll_events = 0
            return True

        if y > 0 or (self._window.is_manga_mode and x < 0) or (
          not self._window.is_manga_mode and x > 0):
            page_flipped = self._next_page_with_protection()
        else:
            page_flipped = self._previous_page_with_protection()

        return not page_flipped

    def _scroll_down(self):
        """ Scrolls down. """
        self._scroll_with_flipping(0, prefs['number of pixels to scroll per key event'])

    def _scroll_up(self):
        """ Scrolls up. """
        self._scroll_with_flipping(0, -prefs['number of pixels to scroll per key event'])

    def _scroll_right(self):
        """ Scrolls right. """
        self._scroll_with_flipping(prefs['number of pixels to scroll per key event'], 0)

    def _scroll_left(self):
        """ Scrolls left. """
        self._scroll_with_flipping(-prefs['number of pixels to scroll per key event'], 0)

    def _smart_scroll_down(self, small_step=None):
        """ Smart scrolling. """
        self._smart_scrolling(small_step, False)

    def _smart_scroll_up(self, small_step=None):
        """ Reversed smart scrolling. """
        self._smart_scrolling(small_step, True)

    def _smart_scrolling(self, small_step, backwards):
        # Collect data from the environment
        viewport_size = self._window.get_visible_area_size()
        distance = prefs['smart scroll percentage']
        if small_step is None:
            max_scroll = [distance * viewport_size[0],
                distance * viewport_size[1]] # 2D only
        else:
            max_scroll = [small_step] * 2 # 2D only
        swap_axes = constants.SWAPPED_AXES if prefs['invert smart scroll'] \
            else constants.NORMAL_AXES
        self._window.update_layout_position()

        # Scroll to the new position
        new_index = self._window.layout.scroll_smartly(max_scroll, backwards, swap_axes)
        n = 2 if self._window.displayed_double() else 1 # XXX limited to at most 2 pages

        if new_index == -1:
            self._previous_page_with_protection()
        elif new_index == n:
            self._next_page_with_protection()
        else:
            # Update actual viewport
            self._window.update_viewport_position()


    def _next_page_with_protection(self):
        """ Advances to the next page. If L{_scroll_protection} is enabled,
        this method will only advance if enough scrolling attempts have been made.

        @return: True when the page was flipped."""

        if not prefs['flip with wheel']:
            self._extra_scroll_events = 0
            return False

        if (not self._scroll_protection
            or self._extra_scroll_events >= prefs['number of key presses before page turn'] - 1
            or not self._window.is_scrollable()):

            self._flip_page(1)
            return True

        elif (self._scroll_protection):
            self._extra_scroll_events = max(1, self._extra_scroll_events + 1)
            return False

        else:
            # This path should not be reached.
            assert False, "Programmer is moron, incorrect assertion."

    def _previous_page_with_protection(self):
        """ Goes back to the previous page. If L{_scroll_protection} is enabled,
        this method will only go back if enough scrolling attempts have been made.

        @return: True when the page was flipped."""

        if not prefs['flip with wheel']:
            self._extra_scroll_events = 0
            return False

        if (not self._scroll_protection
            or self._extra_scroll_events <= -prefs['number of key presses before page turn'] + 1
            or not self._window.is_scrollable()):

            self._flip_page(-1)
            return True

        elif (self._scroll_protection):
            self._extra_scroll_events = min(-1, self._extra_scroll_events - 1)
            return False

        else:
            # This path should not be reached.
            assert False, "Programmer is moron, incorrect assertion."


    def _flip_page(self, number_of_pages, single_step=False):
        """ Switches a number of pages forwards/backwards. If C{single_step} is True,
        the page count will be advanced by only one page even in double page mode. """
        self._extra_scroll_events = 0
        self._window.flip_page(number_of_pages, single_step=single_step)

    def _left_right_page_progress(self, number_of_pages=1):
        """ If number_of_pages is positive, this function advances the specified
        number of pages in manga mode and goes back the same number of pages in
        normal mode. The opposite happens for number_of_pages being negative. """
        self._flip_page(-number_of_pages if self._window.is_manga_mode else number_of_pages)

    def _execute_command(self, cmdindex):
        """ Execute an external command. cmdindex should be an integer from 0 to 9,
        representing the command that should be executed. """
        manager = openwith.OpenWithManager()
        commands = [cmd for cmd in manager.get_commands() if not cmd.is_separator()]
        if len(commands) > cmdindex:
            commands[cmdindex].execute(self._window)


def _get_latest_event_of_same_type(event):
    """Return the latest event in the event queue that is of the same type
    as <event>, or <event> itself if no such events are in the queue. All
    events of that type will be removed from the event queue.
    """
    events = []

    while gtk.gdk.events_pending():
        queued_event = gtk.gdk.event_get()

        if queued_event is not None:

            if queued_event.type == event.type:
                event = queued_event
            else:
                events.append(queued_event)

    for queued_event in events:
        queued_event.put()

    return event


def _valwarp(cur, maxval, minval=0, tolerance=3, extra=2):
    """ Helper function for warping the cursor around the screen when it
      comes within `tolerance` to a border (and `extra` more to avoid
      jumping back and forth).  """
    if cur < minval + tolerance:
        overmove = minval + tolerance - cur
        return maxval - tolerance - overmove - extra
    if (maxval - cur) < tolerance:
        overmove = tolerance - (maxval - cur)
        return minval + tolerance + overmove + extra
    return cur


# vim: expandtab:sw=4:ts=4
