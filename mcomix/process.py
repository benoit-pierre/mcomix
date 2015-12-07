"""process.py - Process spawning module."""

import gc
import sys
import os
from distutils import spawn

from mcomix import log
from mcomix import i18n

if 'win32' == sys.platform:
    from mcomix import win32popen
    import subprocess
else:
    try:
        import subprocess32 as subprocess
        _using_subprocess32 = True
    except ImportError:
        log.warning('subprocess32 not available! using subprocess')
        import subprocess
        _using_subprocess32 = False


NULL = open(os.devnull, 'r+b')
PIPE = subprocess.PIPE
STDOUT = subprocess.STDOUT


if 'win32' == sys.platform:

    _exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # Cannot spawn processes with Python/Win32 unless stdin
    # and stderr are redirected to a pipe/devnull as well.
    def call(args, stdin=NULL, stdout=NULL, stderr=NULL, noconsole=True):
        try:
            proc = win32popen.Win32Popen(args,
                                         stdin=stdin,
                                         stdout=stdout,
                                         stderr=stderr,
                                         noconsole=noconsole)
            proc.wait()
        except cpytes.WinError as e:
            log.error('call(%s) failed: %s', ' '.join(args), e)
            return False
        return True

    def popen(args, stdin=NULL, stdout=PIPE, stderr=NULL, noconsole=True):
        return win32popen.Win32Popen(args,
                                     stdin=stdin,
                                     stdout=stdout,
                                     stderr=stderr,
                                     noconsole=noconsole)

else:

    def call(args, stdin=NULL, stdout=NULL, stderr=NULL, noconsole=True):
        return 0 == subprocess.call(args,
                                    stdin=stdin,
                                    stdout=stdout,
                                    stderr=stderr)

    def popen(args, stdin=NULL, stdout=PIPE, stderr=NULL, noconsole=True):
        if not _using_subprocess32:
            gc.disable() # Avoid Python issue #1336!
        try:
            return subprocess.Popen(args,
                                    stdin=stdin,
                                    stdout=stdout,
                                    stderr=stderr)
        finally:
            if not _using_subprocess32:
                gc.enable()


def find_executable(candidates, workdir=None):
    """ Find executable in path.

    Return an absolute path to a valid executable or None.

    <workdir> default to the current working directory if not set.

    If a candidate has a directory component,
    it will be checked relative to <workdir>.

    On Windows:

    - '.exe' will be appended to each candidate if not already

    - MComix executable directory is prepended to the path on Windows
      (to support embedded tools/executables in the distribution).

    - <workdir> will be inserted first in the path.

    On Unix:

    - a valid candidate must have execution right

    """
    if workdir is None:
        workdir = os.getcwd()
    workdir = os.path.abspath(workdir)

    search_path = os.environ['PATH'].split(os.pathsep)
    if 'win32' == sys.platform:
        if workdir is not None:
            search_path.insert(0, workdir)
        search_path.insert(0, _exe_dir)

    valid_exe = lambda exe: \
            os.path.isfile(exe) and \
            os.access(exe, os.R_OK|os.X_OK)

    for name in candidates:

        # On Windows, must end with '.exe'
        if 'win32' == sys.platform:
            if not name.endswith('.exe'):
                name = name + '.exe'

        # Absolute path?
        if os.path.isabs(name):
            if valid_exe(name):
                return name

        # Does candidate have a directory component?
        elif os.path.dirname(name):
            # Yes, check relative to working directory.
            path = os.path.normpath(os.path.join(workdir, name))
            if valid_exe(path):
                return path

        # Look in search path.
        else:
            for dir in search_path:
                path = os.path.abspath(os.path.join(dir, name))
                if valid_exe(path):
                    return path

    return None

# vim: expandtab:sw=4:ts=4
