
import os
import sys
import optparse
import signal

if __name__ == '__main__':
    print >> sys.stderr, 'PROGRAM TERMINATED'
    print >> sys.stderr, 'Please do not run this script directly! Use mcomixstarter.py instead.'
    sys.exit(1)

# These modules must not depend on GTK, pkg_resources, PIL,
# or any other optional libraries.
from mcomix import (
    constants,
    log,
    portability,
    preferences,
)

def wait_and_exit(code=1):
    """ Wait for the user pressing ENTER before closing. This should help
    the user find possibly missing dependencies when starting, since the
    Python window will not close down immediately after the error. """
    if sys.platform == 'win32' and not sys.stdin.closed and not sys.stdout.closed:
        print
        raw_input("Press ENTER to continue...")
    sys.exit(code)

class OptionParser(optparse.OptionParser):

    def __init__(self):
        optparse.OptionParser.__init__(
            self,
            add_help_option=False,
            usage="%%prog %s" % _('[OPTION...] [PATH]'),
            description=_('View images and comic book archives.'),
        )
        self.add_option('--help', action='help',
                        help=_('Show this help and exit.'))
        self.add_option('-s', '--slideshow', dest='slideshow', action='store_true',
                        help=_('Start the application in slideshow mode.'))
        self.add_option('-l', '--library', dest='library', action='store_true',
                        help=_('Show the library on startup.'))
        self.add_option('-v', '--version', action='callback', callback=self.print_version,
                        help=_('Show the version number and exit.'))
        if sys.platform == 'win32':
            self.add_option('--no-update-fontconfig-cache',
                            dest='update_fontconfig_cache',
                            default=True, action='store_false',
                            help=_('Don\'t update fontconfig cache at startup.'))
        else:
            self.add_option('--update-fontconfig-cache',
                            dest='update_fontconfig_cache',
                            default=False, action='store_true',
                            help=_('Update fontconfig cache at startup.'))

        viewmodes = optparse.OptionGroup(self, _('View modes'))
        viewmodes.add_option('-f', '--fullscreen', dest='fullscreen', action='store_true',
                             help=_('Start the application in fullscreen mode.'))
        viewmodes.add_option('-m', '--manga', dest='manga', action='store_true',
                             help=_('Start the application in manga mode.'))
        viewmodes.add_option('-d', '--double-page', dest='doublepage', action='store_true',
                             help=_('Start the application in double page mode.'))
        self.add_option_group(viewmodes)

        fitmodes = optparse.OptionGroup(self, _('Zoom modes'))
        fitmodes.add_option('-b', '--zoom-best', dest='zoommode', action='store_const',
                            const=constants.ZOOM_MODE_BEST,
                            help=_('Start the application with zoom set to best fit mode.'))
        fitmodes.add_option('-w', '--zoom-width', dest='zoommode', action='store_const',
                            const=constants.ZOOM_MODE_WIDTH,
                            help=_('Start the application with zoom set to fit width.'))
        fitmodes.add_option('-h', '--zoom-height', dest='zoommode', action='store_const',
                            const=constants.ZOOM_MODE_HEIGHT,
                            help=_('Start the application with zoom set to fit height.'))
        self.add_option_group(fitmodes)

        debugopts = optparse.OptionGroup(self, _('Debug options'))
        debugopts.add_option('-W', dest='loglevel', action='store', default='warn',
                             choices=('all', 'debug', 'info', 'warn', 'error'),
                             metavar='[ all | debug | info | warn | error ]',
                             help=_('Sets the desired output log level.'))
        # This supresses an error when MComix is used with cProfile
        debugopts.add_option('-o', dest='output', action='store',
                             default='', help=optparse.SUPPRESS_HELP)
        self.add_option_group(debugopts)

    def print_version(self, opt, value, parser, *args, **kwargs):
        """Print the version number and exit."""
        self.exit(msg='%s %s\n' % (constants.APPNAME, constants.VERSION))

    def exit(self, status=0, msg=None):
        if msg:
            sys.stderr.write(msg)
        wait_and_exit(status)

def parse_arguments(argv):
    """ Parse the command line passed in <argv>. Returns a tuple containing
    (options, arguments). Errors parsing the command line are handled in
    this function. """
    parser = OptionParser()
    opts, args = parser.parse_args(argv)
    # Fix up log level to use constants from log.
    if opts.loglevel == 'all':
        opts.loglevel = log.DEBUG
    if opts.loglevel == 'debug':
        opts.loglevel = log.DEBUG
    if opts.loglevel == 'info':
        opts.loglevel = log.INFO
    elif opts.loglevel == 'warn':
        opts.loglevel = log.WARNING
    elif opts.loglevel == 'error':
        opts.loglevel = log.ERROR
    return opts, args

def run():
    """Run the program."""

    try:
        import pkg_resources

    except ImportError:
        # gettext isn't initialized yet, since pkg_resources is required to find translation files.
        # Thus, localizing these messages is pointless.
        log._print("The package 'pkg_resources' could not be found.")
        log._print("You need to install the 'setuptools' package, which also includes pkg_resources.")
        log._print("Note: On most distributions, 'distribute' supersedes 'setuptools'.")
        wait_and_exit()

    # Load configuration and setup localisation.
    preferences.read_preferences_file()
    from mcomix import i18n
    i18n.install_gettext()

    # Retrieve and parse command line arguments.
    argv = portability.get_commandline_args()
    opts, args = parse_arguments(argv)

    # First things first: set the log level.
    log.setLevel(opts.loglevel)

    # On Windows, update the fontconfig cache manually, before MComix starts
    # using Gtk, since the process may take several minutes, during which the
    # main window will just be frozen if the work is left to Gtk itself...
    if opts.update_fontconfig_cache:
        # First, update fontconfig cache.
        log.debug('starting fontconfig cache update')
        try:
            from mcomix.win32 import fc_cache
            from mcomix.process import find_executable
            fc_cache.update()
            log.debug('fontconfig cache updated')
        except Exception as e:
            log.error('during fontconfig cache update', exc_info=e)
        # And then replace current MComix process with a fresh one
        # (that will not try to update the cache again).
        exe = sys.argv[0]
        if sys.platform == 'win32' and exe.endswith('.py'):
            # Find the interpreter.
            args = [exe, sys.argv[0]]
            exe = find_executable(('pythonw.exe', 'python.exe'))
        else:
            args = [exe]
        if sys.platform == 'win32':
            args.append('--no-update-fontconfig-cache')
        args.extend(sys.argv[1:])
        if '--update-fontconfig-cache' in args:
            args.remove('--update-fontconfig-cache')
        log.debug('restarting MComix from fresh: os.execv(%s, %s)', repr(exe), args)
        try:
            os.execv(exe, args)
        except Exception as e:
            log.error('os.execv(%s, %s) failed', exe, str(args), exc_info=e)
        wait_and_exit()

    # Check for PyGTK and PIL dependencies.
    try:
        import pygtk
        pygtk.require('2.0')

        import gtk
        assert gtk.gtk_version >= (2, 12, 0)
        assert gtk.pygtk_version >= (2, 12, 0)

        import gobject
        gobject.threads_init()

    except AssertionError:
        log.error( _("You do not have the required versions of GTK+ and PyGTK installed.") )
        log.error( _('Installed GTK+ version is: %s') % \
                  '.'.join([str(n) for n in gtk.gtk_version]) )
        log.error( _('Required GTK+ version is: 2.12.0 or higher') )
        log.error( _('Installed PyGTK version is: %s') % \
                  '.'.join([str(n) for n in gtk.pygtk_version]) )
        log.error( _('Required PyGTK version is: 2.12.0 or higher') )
        wait_and_exit()

    except ImportError:
        log.error( _('Required PyGTK version is: 2.12.0 or higher') )
        log.error( _('No version of PyGTK was found on your system.') )
        log.error( _('This error might be caused by missing GTK+ libraries.') )
        wait_and_exit()

    try:
        import PIL.Image
        assert PIL.Image.VERSION >= '1.1.5'

    except AssertionError:
        log.error( _("You don't have the required version of the Python Imaging"), end=' ')
        log.error( _('Library (PIL) installed.') )
        log.error( _('Installed PIL version is: %s') % Image.VERSION )
        log.error( _('Required PIL version is: 1.1.5 or higher') )
        wait_and_exit()

    except ImportError:
        log.error( _('Python Imaging Library (PIL) 1.1.5 or higher is required.') )
        log.error( _('No version of the Python Imaging Library was found on your system.') )
        wait_and_exit()

    if not os.path.exists(constants.DATA_DIR):
        os.makedirs(constants.DATA_DIR, 0700)

    if not os.path.exists(constants.CONFIG_DIR):
        os.makedirs(constants.CONFIG_DIR, 0700)

    from mcomix import icons
    icons.load_icons()

    open_path = None
    open_page = 1
    if len(args) == 1:
        open_path = args[0]
    elif len(args) > 1:
        open_path = args

    elif preferences.prefs['auto load last file'] \
        and preferences.prefs['path to last file'] \
        and os.path.isfile(preferences.prefs['path to last file']):
        open_path = preferences.prefs['path to last file']
        open_page = preferences.prefs['page of last file']

    # Some languages require a RTL layout
    if preferences.prefs['language'] in ('he', 'fa'):
        gtk.widget_set_default_direction(gtk.TEXT_DIR_RTL)

    gtk.gdk.set_program_class(constants.APPNAME)

    from mcomix import main
    window = main.MainWindow(fullscreen = opts.fullscreen, is_slideshow = opts.slideshow,
            show_library = opts.library, manga_mode = opts.manga,
            double_page = opts.doublepage, zoom_mode = opts.zoommode,
            open_path = open_path, open_page = open_page)
    main.set_main_window(window)

    if 'win32' != sys.platform:
        # Add a SIGCHLD handler to reap zombie processes.
        def on_sigchld(signum, frame):
            try:
                os.waitpid(-1, os.WNOHANG)
            except OSError:
                pass
        signal.signal(signal.SIGCHLD, on_sigchld)

    signal.signal(signal.SIGTERM, lambda: gobject.idle_add(window.terminate_program))
    try:
        gtk.main()
    except KeyboardInterrupt: # Will not always work because of threading.
        window.terminate_program()

# vim: expandtab:sw=4:ts=4
