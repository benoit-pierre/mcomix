"""library_control_area.py - The window in the library that contains buttons
and displays info."""

import os
import gtk
import gobject
import pango

from mcomix import i18n
from mcomix import labels
from mcomix.library.watchlist import WatchListDialog

# The "All books" collection is not a real collection stored in the library,
# but is represented by this ID in the library's TreeModels.
_COLLECTION_ALL = -1


class _ControlArea(gtk.HBox):

    """The _ControlArea is the bottom area of the library window where
    information is displayed and controls such as buttons reside.
    """

    def __init__(self, library):
        super(_ControlArea, self).__init__(False, 12)

        self._library = library
        self.set_border_width(10)

        borderbox = gtk.Frame()
        borderbox.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        borderbox.set_size_request(350, -1)

        insidebox = gtk.EventBox()
        insidebox.set_border_width(1)
        insidebox.set_state(gtk.STATE_ACTIVE)

        infobox = gtk.VBox(False, 5)
        infobox.set_border_width(10)
        self.pack_start(borderbox)
        borderbox.add(insidebox)
        insidebox.add(infobox)

        self._namelabel = labels.BoldLabel()
        self._namelabel.set_alignment(0, 0.5)
        self._namelabel.set_selectable(True)
        self._namelabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        infobox.pack_start(self._namelabel, False, False)

        self._filelabel = gtk.Label()
        self._filelabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self._filelabel.set_alignment(0, 0.5)
        infobox.pack_start(self._filelabel, False, False)

        self._dirlabel = gtk.Label()
        self._dirlabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self._dirlabel.set_alignment(0, 0.5)
        self._dirlabel.set_selectable(True)
        infobox.pack_start(self._dirlabel, False, False)

        vbox = gtk.VBox(False, 10)
        vbox.set_size_request(250, -1)
        self.pack_start(vbox, False, False)

        # First line of controls, containing the search box
        hbox = gtk.HBox(False)
        vbox.pack_start(hbox, False, False)

        label = gtk.Label(_('_Search:'))
        label.set_use_underline(True)
        hbox.pack_start(label, False, False)
        search_entry = gtk.Entry()
        search_entry.connect('activate', self._filter_books)
        search_entry.set_tooltip_text(
            _('Display only those books that have the specified text string '
              'in their full path. The search is not case sensitive.'))
        hbox.pack_start(search_entry, True, True, 6)
        label.set_mnemonic_widget(search_entry)

        # Last line of controls, containing buttons like 'Open'
        hbox = gtk.HBox(True, 10)
        vbox.pack_end(hbox)

        watchlist_button = gtk.Button(_("_Watch list"))
        watchlist_button.set_image(
            gtk.image_new_from_stock(gtk.STOCK_FIND, gtk.ICON_SIZE_BUTTON))
        watchlist_button.connect('clicked',
            lambda *args: WatchListDialog(self._library))
        watchlist_button.set_tooltip_text(
            _('Open the watchlist management dialog.'))
        hbox.pack_start(watchlist_button, expand=False)

        self._open_button = gtk.Button(None, gtk.STOCK_OPEN)
        self._open_button.connect('clicked',
            self._library.book_area.open_selected_book)
        self._open_button.set_tooltip_text(_('Open the selected book.'))
        self._open_button.set_sensitive(False)
        hbox.pack_end(self._open_button, expand=False)

    def update_info(self, selected):
        """Update the info box using the currently <selected> books from
        the _BookArea.
        """

        if selected:
            book_id = self._library.book_area.get_book_at_path(selected[0])
            book = self._library.backend.get_book_by_id(book_id)
        else:
            book = None

        if book:
            name = book.name
            dir_path = os.path.dirname(book.path)
            pages = book.pages
            size = book.size
            last_page = book.get_last_read_page()
            last_date = book.get_last_read_date()
        else:
            name = dir_path = pages = size = last_page = last_date = None

        if len(selected) > 0:
            self._open_button.set_sensitive(True)
        else:
            self._open_button.set_sensitive(False)

        if name is not None:
            self._namelabel.set_text(i18n.to_unicode(name))
            self._namelabel.set_tooltip_text(i18n.to_unicode(name))
        else:
            self._namelabel.set_text('')
            self._namelabel.set_has_tooltip(False)

        infotext = []

        if last_page is not None and pages is not None and last_page != pages:
            infotext.append('%s %d/%d' % (_('Page'), last_page, pages))
        elif pages is not None:
            infotext.append(_('%d pages') % pages)

        if size is not None:
            infotext.append('%.1f MiB' % (size / 1048576.0))

        if (pages is not None and last_page is not None and
            last_date is not None and last_page == pages):
            infotext.append(_('Finished reading on %(date)s, %(time)s') % {
                'date': last_date.strftime('%x'),
                'time': last_date.strftime('%X') })

        self._filelabel.set_text(', '.join(infotext))

        if dir_path is not None:
            self._dirlabel.set_text(i18n.to_unicode(dir_path))
        else:
            self._dirlabel.set_text('')

    def _filter_books(self, entry, *args):
        """Display only the books in the current collection whose paths
        contain the string in the gtk.Entry. The string is not
        case-sensitive.
        """
        self._library.filter_string = entry.get_text().decode('utf-8')
        if not self._library.filter_string:
            self._library.filter_string = None
        collection = self._library.collection_area.get_current_collection()
        gobject.idle_add(self._library.book_area.display_covers, collection)

# vim: expandtab:sw=4:ts=4
