
import _subprocess
import subprocess
import msvcrt
import ctypes
import os

from mcomix import i18n


# Declare common data types
DWORD = ctypes.c_uint
WORD = ctypes.c_ushort
LPTSTR = ctypes.c_wchar_p
LPBYTE = ctypes.POINTER(ctypes.c_ubyte)
HANDLE = ctypes.c_void_p

class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", DWORD),
        ("lpReserved", LPTSTR),
        ("lpDesktop", LPTSTR),
        ("lpTitle", LPTSTR),
        ("dwX", DWORD),
        ("dwY", DWORD),
        ("dwXSize", DWORD),
        ("dwYSize", DWORD),
        ("dwXCountChars", DWORD),
        ("dwYCountChars", DWORD),
        ("dwFillAttribute", DWORD),
        ("dwFlags", DWORD),
        ("wShowWindow", WORD),
        ("cbReserved2", WORD),
        ("lpReserved2", LPBYTE),
        ("hStdInput", HANDLE),
        ("hStdOutput", HANDLE),
        ("hStdError", HANDLE)]

class ProcessInformation(ctypes.Structure):
    _fields_ = [("hProcess", HANDLE),
        ("hThread", HANDLE),
        ("dwProcessId", DWORD),
        ("dwThreadId", DWORD)]

LPSTRARTUPINFO = ctypes.POINTER(StartupInfo)
LPROCESS_INFORMATION = ctypes.POINTER(ProcessInformation)
ctypes.windll.kernel32.CreateProcessW.argtypes = [LPTSTR, LPTSTR,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool, DWORD,
    ctypes.c_void_p, LPTSTR, LPSTRARTUPINFO, LPROCESS_INFORMATION]
ctypes.windll.kernel32.CreateProcessW.restype = ctypes.c_bool


# Keep track of delete instances that were still active.

_active = []

def _cleanup():
    for inst in _active[:]:
        res = inst._internal_poll()
        if res is not None:
            try:
                _active.remove(inst)
            except ValueError:
                # This can happen if two threads create a new Popen instance.
                # It's harmless that it was already removed, so ignore.
                pass


class Win32Popen(object):

    def __init__(self, cmd, stdin=None, stdout=None, stderr=None, noconsole=True):
        """ Spawns a new process on Win32. cmd is a list of parameters.
        This is a (partial) reimplementation of subprocess.Popen using
        CreateProcessW instead of CreateProcessA.
        """

        # Cleanup existing instances.
        _cleanup()

        self._child_created = False
        self.returncode = None

        # Convert list of arguments into a single string
        cmdline = subprocess.list2cmdline(cmd)
        buffer = ctypes.create_unicode_buffer(cmdline)

        # Resolve executable path.
        from mcomix.process import find_executable
        exe = find_executable((cmd[0],))

        # Some required structures for the method call...
        startupinfo = StartupInfo()
        ctypes.memset(ctypes.addressof(startupinfo), 0, ctypes.sizeof(startupinfo))
        startupinfo.cb = ctypes.sizeof(startupinfo)
        processinfo = ProcessInformation()

        (p2cread, p2cwrite,
         c2pread, c2pwrite,
         errread, errwrite) = self._get_handles(stdin, stdout, stderr)

        if -1 not in (p2cread, c2pwrite, errwrite):
            startupinfo.dwFlags |= _subprocess.STARTF_USESTDHANDLES
            startupinfo.hStdInput = int(p2cread)
            startupinfo.hStdOutput = int(c2pwrite)
            startupinfo.hStdError = int(errwrite)

        if p2cwrite != -1:
            p2cwrite = msvcrt.open_osfhandle(p2cwrite.Detach(), 0)
        if c2pread != -1:
            c2pread = msvcrt.open_osfhandle(c2pread.Detach(), 0)
        if errread != -1:
            errread = msvcrt.open_osfhandle(errread.Detach(), 0)

        if p2cwrite != -1:
            self.stdin = os.fdopen(p2cwrite, 'wb', 0)
        if c2pread != -1:
            self.stdout = os.fdopen(c2pread, 'rb', 0)
        if errread != -1:
            self.stderr = os.fdopen(errread, 'rb', 0)

        creationflags = 0
        if noconsole:
            # Do not create a console window.
            creationflags |= 0x08000000

        # Spawn new process.
        success = ctypes.windll.kernel32.CreateProcessW(exe,
                                                        buffer,
                                                        None,
                                                        None,
                                                        False,
                                                        creationflags,
                                                        None,
                                                        None,
                                                        ctypes.byref(startupinfo),
                                                        ctypes.byref(processinfo))
        if not success:
            raise ctypes.WinError(ctypes.GetLastError(),
                                  i18n.to_unicode(ctypes.FormatError()))

        self._child_created = True
        self.pid = processinfo.dwProcessId
        self._handle = processinfo.hProcess
        ctypes.windll.kernel32.CloseHandle(processinfo.hThread)

    def poll(self):
        return self._internal_poll()

    def wait(self):
        """Wait for child process to terminate.  Returns returncode
        attribute."""
        if self.returncode is None:
            _subprocess.WaitForSingleObject(self._handle,
                                            _subprocess.INFINITE)
            self.returncode = _subprocess.GetExitCodeProcess(self._handle)
        return self.returncode

    def __del__(self):
        # If __init__ hasn't had a chance to execute (e.g. if it
        # was passed an undeclared keyword argument), we don't
        # have a _child_created attribute at all.
        if not self._child_created:
            # We didn't get to successfully create a child process.
            return
        # In case the child hasn't been waited on, check if it's done.
        self._internal_poll()
        if self.returncode is None and _active is not None:
            # Child is still running, keep us alive until we can wait on it.
            _active.append(self)

    def _internal_poll(self):
        """Check if child process has terminated.  Returns returncode
        attribute.

        This method is called by __del__, so it can only refer to objects
        in its local scope.

        """
        if self.returncode is None:
            if _subprocess.WaitForSingleObject(self._handle, 0) == _subprocess.WAIT_OBJECT_0:
                self.returncode = _subprocess.GetExitCodeProcess(self._handle)
        return self.returncode

    def _get_handles(self, stdin, stdout, stderr):
        """Construct and return tuple with IO objects:
        p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
        """
        if stdin is None and stdout is None and stderr is None:
            return (-1, -1, -1, -1, -1, -1)

        p2cread, p2cwrite = -1, -1
        c2pread, c2pwrite = -1, -1
        errread, errwrite = -1, -1

        if stdin is None:
            p2cread = _subprocess.GetStdHandle(_subprocess.STD_INPUT_HANDLE)
            if p2cread is None:
                p2cread, _ = _subprocess.CreatePipe(None, 0)
        elif stdin == subprocess.PIPE:
            p2cread, p2cwrite = _subprocess.CreatePipe(None, 0)
        elif isinstance(stdin, int):
            p2cread = msvcrt.get_osfhandle(stdin)
        else:
            # Assuming file-like object
            p2cread = msvcrt.get_osfhandle(stdin.fileno())
        p2cread = self._make_inheritable(p2cread)

        if stdout is None:
            c2pwrite = _subprocess.GetStdHandle(_subprocess.STD_OUTPUT_HANDLE)
            if c2pwrite is None:
                _, c2pwrite = _subprocess.CreatePipe(None, 0)
        elif stdout == subprocess.PIPE:
            c2pread, c2pwrite = _subprocess.CreatePipe(None, 0)
        elif isinstance(stdout, int):
            c2pwrite = msvcrt.get_osfhandle(stdout)
        else:
            # Assuming file-like object
            c2pwrite = msvcrt.get_osfhandle(stdout.fileno())
        c2pwrite = self._make_inheritable(c2pwrite)

        if stderr is None:
            errwrite = _subprocess.GetStdHandle(_subprocess.STD_ERROR_HANDLE)
            if errwrite is None:
                _, errwrite = _subprocess.CreatePipe(None, 0)
        elif stderr == subprocess.PIPE:
            errread, errwrite = _subprocess.CreatePipe(None, 0)
        elif stderr == subprocess.STDOUT:
            errwrite = c2pwrite
        elif isinstance(stderr, int):
            errwrite = msvcrt.get_osfhandle(stderr)
        else:
            # Assuming file-like object
            errwrite = msvcrt.get_osfhandle(stderr.fileno())
        errwrite = self._make_inheritable(errwrite)

        return (p2cread, p2cwrite,
                c2pread, c2pwrite,
                errread, errwrite)

    def _make_inheritable(self, handle):
        """Return a duplicate of handle, which is inheritable"""
        return _subprocess.DuplicateHandle(_subprocess.GetCurrentProcess(),
                                           handle,
                                           _subprocess.GetCurrentProcess(),
                                           0, 1,
                                           _subprocess.DUPLICATE_SAME_ACCESS)


