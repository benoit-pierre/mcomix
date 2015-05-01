"""status.py - Statusbar for main window."""

import gtk

from mcomix import i18n
from mcomix import constants
from mcomix.preferences import prefs

class Statusbar(gtk.EventBox):

    SPACING = 5

    def __init__(self):
        super(Statusbar, self).__init__()

        self._loading = True

        # Status text, page number, file number, resolution, path, filename
        self.status = gtk.Statusbar()
        self.add(self.status)

        # Create popup menu for enabling/disabling status boxes.
        self.ui_manager = gtk.UIManager()
        self.tooltipstatus = TooltipStatusHelper(self.ui_manager, self.status)
        ui_description = """
        <ui>
            <popup name="Statusbar">
                <menuitem action="pagenumber" />
                <menuitem action="filenumber" />
                <menuitem action="resolution" />
                <menuitem action="rootpath" />
                <menuitem action="filename" />
            </popup>
        </ui>
        """
        self.ui_manager.add_ui_from_string(ui_description)

        actiongroup = gtk.ActionGroup('mcomix-statusbar')
        actiongroup.add_toggle_actions([
            ('pagenumber', None, _('Show page numbers'), None, None,
                self.toggle_status_visibility),
            ('filenumber', None, _('Show file numbers'), None, None,
                self.toggle_status_visibility),
            ('resolution', None, _('Show resolution'), None, None,
                self.toggle_status_visibility),
            ('rootpath', None, _('Show path'), None, None,
                self.toggle_status_visibility),
            ('filename', None, _('Show filename'), None, None,
                self.toggle_status_visibility)])
        self.ui_manager.insert_action_group(actiongroup, 0)

        # Hook mouse release event
        self.connect('button-release-event', self._button_released)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|gtk.gdk.BUTTON_RELEASE_MASK)

        # Default status information
        self._page_info = ''
        self._file_info = ''
        self._resolution = ''
        self._root = ''
        self._filename = ''
        self._update_sensitivity()
        self.show_all()

        self._loading = False

    def set_message(self, message):
        """Set a specific message (such as an error message) on the statusbar,
        replacing whatever was there earlier.
        """
        self.status.pop(0)
        self.status.push(0, " " * Statusbar.SPACING + message)

    def set_page_number(self, page, total, this_screen):
        """Update the page number."""
        page_info = ""
        for i in range(this_screen):
            page_info += '%d' % (page + i)
            if i < this_screen - 1:
                page_info +=','
        page_info += ' / %d' % total
        self._page_info = page_info

    def get_page_number(self):
        """Returns the bar's page information."""
        return self._page_info

    def set_file_number(self, fileno, total):
        """Updates the file number (i.e. number of current file/total
        files loaded)."""
        if total > 0:
            self._file_info = '(%d / %d)' % (fileno, total)
        else:
            self._file_info = ''

    def get_file_number(self):
        """ Returns the bar's file information."""
        return self._file_info

    def set_resolution(self, dimensions): # 2D only
        """Update the resolution data.

        Takes an iterable of tuples, (x, y, scale), describing the original
        resolution of an image as well as the currently displayed scale.
        """
        resolution = ""
        for i in range(len(dimensions)):
            d = dimensions[i]
            resolution += '%dx%d (%.1f%%)' % (d[0], d[1], d[2] * 100.0)
            if i < len(dimensions) - 1:
                resolution += ', '
        self._resolution = resolution

    def set_root(self, root):
        """Set the name of the root (directory or archive)."""
        self._root = i18n.to_unicode(root)

    def set_filename(self, filename):
        """Update the filename."""
        self._filename = i18n.to_unicode(filename)

    def update(self):
        """Set the statusbar to display the current state."""

        space = " " * Statusbar.SPACING
        text = (space + "|" + space).join(self._get_status_text())
        self.status.pop(0)
        self.status.push(0, space + text)

    def push(self, context_id, message):
        """ Compatibility with gtk.Statusbar. """
        assert context_id >= 0
        self.status.push(context_id + 1, message)

    def pop(self, context_id):
        """ Compatibility with gtk.Statusbar. """
        assert context_id >= 0
        self.status.pop(context_id + 1)

    def _get_status_text(self):
        """ Returns an array of text fields that should be displayed. """
        fields = []

        if prefs['statusbar fields'] & constants.STATUS_PAGE:
            fields.append(self._page_info)
        if prefs['statusbar fields'] & constants.STATUS_FILENUMBER:
            fields.append(self._file_info)
        if prefs['statusbar fields'] & constants.STATUS_RESOLUTION:
            fields.append(self._resolution)
        if prefs['statusbar fields'] & constants.STATUS_PATH:
            fields.append(self._root)
        if prefs['statusbar fields'] & constants.STATUS_FILENAME:
            fields.append(self._filename)

        return fields

    def toggle_status_visibility(self, action, *args):
        """ Called when status entries visibility is to be changed. """

        # Ignore events as long as control is still loading.
        if self._loading:
            return

        actionname = action.get_name()
        if actionname == 'pagenumber':
            bit = constants.STATUS_PAGE
        elif actionname == 'resolution':
            bit = constants.STATUS_RESOLUTION
        elif actionname == 'rootpath':
            bit = constants.STATUS_PATH
        elif actionname == 'filename':
            bit = constants.STATUS_FILENAME
        elif actionname == 'filenumber':
            bit = constants.STATUS_FILENUMBER

        if action.get_active():
            prefs['statusbar fields'] |= bit
        else:
            prefs['statusbar fields'] &= ~bit

        self.update()
        self._update_sensitivity()

    def _button_released(self, widget, event, *args):
        """ Triggered when a mouse button is released to open the context
        menu. """
        if event.button == 3:
            self.ui_manager.get_widget('/Statusbar').popup(None, None, None,
                event.button, event.time)

    def _update_sensitivity(self):
        """ Updates the action menu's sensitivity based on user preferences. """

        page_visible = prefs['statusbar fields'] & constants.STATUS_PAGE
        fileno_visible = prefs['statusbar fields'] & constants.STATUS_FILENUMBER
        resolution_visible = prefs['statusbar fields'] & constants.STATUS_RESOLUTION
        path_visible = prefs['statusbar fields'] & constants.STATUS_PATH
        filename_visible = prefs['statusbar fields'] & constants.STATUS_FILENAME

        for name, visible in (('pagenumber', page_visible),
                ('filenumber', fileno_visible),
                ('resolution', resolution_visible),
                ('rootpath', path_visible),
                ('filename', filename_visible)):
            action = self.ui_manager.get_action('/Statusbar/' + name)
            action.set_active(visible)


class TooltipStatusHelper(object):
    """ Attaches to a L{gtk.UIManager} to provide statusbar tooltips when
    selecting menu items. """

    def __init__(self, uimanager, statusbar):
        self._statusbar = statusbar

        uimanager.connect('connect-proxy', self._on_connect_proxy)
        uimanager.connect('disconnect-proxy', self._on_disconnect_proxy)

    def _on_connect_proxy(self, uimgr, action, widget):
        """ Connects the widget's selection handlers to the status bar update.
        """
        tooltip = action.get_property('tooltip')
        if isinstance(widget, gtk.MenuItem) and tooltip:
            cid = widget.connect('select', self._on_item_select, tooltip)
            cid2 = widget.connect('deselect', self._on_item_deselect)
            setattr(widget, 'app::connect-ids', (cid, cid2))

    def _on_disconnect_proxy(self, uimgr, action, widget):
        """ Disconnects the widget's selection handlers. """
        cids = getattr(widget, 'app::connect-ids', ())
        for cid in cids:
            widget.disconnect(cid)

    def _on_item_select(self, menuitem, tooltip):
        self._statusbar.push(0, " " * Statusbar.SPACING + tooltip)

    def _on_item_deselect(self, menuitem):
        self._statusbar.pop(0)

# vim: expandtab:sw=4:ts=4
