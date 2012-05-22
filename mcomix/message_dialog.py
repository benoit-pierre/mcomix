""" Simple extension of gtk.MessageDialog for consistent formating. Also
    supports remembering the dialog result.
"""

import gtk

from mcomix.preferences import prefs


class MessageDialog(gtk.MessageDialog):

    def __init__(self, parent=None, flags=0, type=0, buttons=0):
        """ Creates a dialog window.
        @param parent: Parent window
        @param flags: Dialog flags
        @param type: Dialog icon/type
        @param buttons: Dialog buttons. Can only be a predefined BUTTONS_XXX constant.
        """
        super(MessageDialog, self).__init__(parent=parent, flags=flags, type=type, buttons=buttons)

        #: Unique dialog identifier (for storing 'Do not ask again')
        self.dialog_id = None

        # FIXME: This really shouldn't depend on MessageDialog's internal layout implementation
        self.remember_checkbox = gtk.CheckButton(_('Do not ask again.'))
        self.remember_checkbox.set_no_show_all(True)
        self.remember_checkbox.set_can_focus(False)
        labels_box = self.get_content_area().get_children()[0].get_children()[1]
        labels_box.pack_end(self.remember_checkbox, padding=6)

    def set_text(self, primary, secondary=None):
        """ Formats the dialog's text fields.
        @param primary: Main text.
        @param secondary: Descriptive text.
        """
        if primary:
            self.set_markup('<span weight="bold" size="larger">' +
                primary + '</span>')
        if secondary:
            self.format_secondary_markup(secondary)
        else:
            self.format_secondary_text("")

    def should_remember_choice(self):
        """ Returns True when the dialog choice should be remembered. """
        return self.remember_checkbox.get_active()

    def set_should_remember_choice(self, dialog_id):
        """ This method enables the 'Do not ask again' checkbox.
        @param dialog_id: Unique identifier for the dialog (a string).
        """
        self.remember_checkbox.show()
        self.dialog_id = dialog_id

    def run(self):
        """ Makes the dialog visible and waits for a result. Also destroys
        the dialog after the result has been returned. """

        if self.dialog_id in prefs['stored dialog choices']:
            self.destroy()
            return prefs['stored dialog choices'][self.dialog_id]
        else:
            self.show_all()
            # Prevent checkbox from grabbing focus by only enabling it after show
            self.remember_checkbox.set_can_focus(True)
            result = super(MessageDialog, self).run()

            if (self.should_remember_choice() and
                result not in (gtk.RESPONSE_DELETE_EVENT, gtk.RESPONSE_CANCEL)):
                prefs['stored dialog choices'][self.dialog_id] = int(result)

            self.destroy()
            return result


# vim: expandtab:sw=4:ts=4
