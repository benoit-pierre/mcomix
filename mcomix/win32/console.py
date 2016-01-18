
import win32console
import traceback
import msvcrt
import sys
import os

class PopupConsoleWrapper(object):

    '''stdin/stdout/stderr wrapper for Windows: popup a console on activity.'''

    _console_created = False

    @classmethod
    def _create_console(cls):
        if cls._console_created:
            return
        win32console.AllocConsole()
        cls._console_created = True

    @classmethod
    def _close_console(cls):
        if not cls._console_created:
            return
        win32console.FreeConsole()
        cls._console_created = False

    def __init__ (self, hndl_type, mode):
        self._hndl_type = hndl_type
        self._hndl = None
        self._has_output = False
        self.closed = True
        self.encoding = None
        self.mode = mode

    def _create_handle(self):
        if self._hndl is not None:
            return
        self._create_console()
        self._hndl = win32console.GetStdHandle(self._hndl_type)
        self.closed = False

    def has_output(self):
        return self._has_output

    def isatty(self):
        return True

    def flush(self):
        pass

    def write(self, data):
        self._create_handle()
        self._hndl.WriteConsole(data)
        self._has_output = True

    def read(self, size=512):
        self._create_handle()
        return self._hndl.ReadConsole(size)

    def close(self):
        if self.closed:
            return
        self._hndl.Close()
        self.closed = True

def get_console_type():
    for io in (sys.stdout,
               sys.stderr):
        if isinstance(io, PopupConsoleWrapper):
            return 'popup'
        if not (
            io.__class__.__name__ == 'NullWriter' # No console, PyInstaller executable.
            or io.fileno() == -2                  # No console, e.g. with pythonw.exe.
        ):
            return 'inherited'
    return None

def setup_popup_console():
    sys.stdin = PopupConsoleWrapper(win32console.STD_INPUT_HANDLE, 'r')
    sys.stdout = PopupConsoleWrapper(win32console.STD_OUTPUT_HANDLE, 'w')
    sys.stderr = PopupConsoleWrapper(win32console.STD_ERROR_HANDLE, 'w')

def pause_on_output():
    if get_console_type() != 'popup':
        return
    if not sys.stdout.has_output() and \
       not sys.stderr.has_output():
        return
    print 'Press a key to continue...'
    sys.stdout.flush()
    sys.stderr.flush()
    msvcrt.getch()

