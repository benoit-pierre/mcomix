"""archive_extractor.py - Archive extraction class."""
from __future__ import with_statement

import os
import time
import threading
import traceback

from mcomix import archive_tools
from mcomix import callback
from mcomix import log
from mcomix.preferences import prefs
from mcomix.worker_thread import WorkerThread

class Extractor(object):

    """Extractor is a threaded class for extracting different archive formats.

    The Extractor can be loaded with paths to archives and a path to a
    destination directory. Once an archive has been set and its contents
    listed, it is possible to filter out the files to be extracted and set the
    order in which they should be extracted.  The extraction can then be
    started in a new thread in which files are extracted one by one, and a
    signal is sent on a condition after each extraction, so that it is possible
    for other threads to wait on specific files to be ready.

    Note: Support for gzip/bzip2 compressed tar archives is limited, see
    set_files() for more info.
    """

    def __init__(self):
        self._setupped = False

    def setup(self, src, dst, type=None):
        """Setup the extractor with archive <src> and destination dir <dst>.
        Return a threading.Condition related to the is_ready() method, or
        None if the format of <src> isn't supported.
        """
        self._start_time = time.time()
        self._src = src
        self._dst = dst
        # List of archive entries.
        self._contents = []
        # List of (name, path) entries to extract.
        self._files = []
        self._extracted = set()
        self._archive = archive_tools.get_recursive_archive_handler(src, dst, type=type)
        if self._archive is None:
            msg = _('Non-supported archive format: %s') % os.path.basename(src)
            log.warning(msg)
            raise ArchiveException(msg)

        self._contents_listed = False
        self._extract_started = False
        self._condition = threading.Condition()
        self._list_thread = WorkerThread(self._list_contents, name='list')
        self._list_thread.append_order(self._archive)
        self._setupped = True

        return self._condition

    def get_files(self):
        """Return the list of files the extractor is set for extracting.
        """
        with self._condition:
            return self._files[:]

    def get_contents(self):
        """Return a list of archive members.
        """
        with self._condition:
            if not self._contents_listed:
                return []
            return self._contents

    def get_directory(self):
        """Returns the root extraction directory of this extractor."""
        return self._dst

    def set_files(self, files):
        """Set the files that the extractor should extract from the archive in
        the order of extraction. Normally one would get the list of all files
        in the archive using get_contents(), then filter and/or permute this
        list before sending back a list of (archive name, extracted name)
        using set_files().

        Note: Random access on gzip or bzip2 compressed tar archives is
        no good idea. These formats are supported *only* for backwards
        compability. They are fine formats for some purposes, but should
        not be used for scanned comic books. So, we cheat and ignore the
        ordering applied with this method on such archives.
        """
        with self._condition:
            if not self._contents_listed:
                return
            self._files = [(name, extracted_name)
                           for name, extracted_name in files
                           if name not in self._extracted]
            if self._extract_started:
                self.extract()

    def is_ready(self, name):
        """Return True if the file <name> in the extractor's file list
        (as set by set_files()) is fully extracted.
        """
        with self._condition:
            return name in self._extracted

    def stop(self):
        """Signal the extractor to stop extracting and kill the extracting
        thread. Blocks until the extracting thread has terminated.
        """
        if self._setupped:
            self._list_thread.stop()
            if self._extract_started:
                self._extract_thread.stop()
                self._extract_started = False
            self.setupped = False

    def extract(self):
        """Start extracting the files in the file list one by one using a
        new thread. Every time a new file is extracted a notify() will be
        signalled on the Condition that was returned by setup().
        """
        with self._condition:
            if not self._contents_listed:
                return
            if not self._extract_started:
                if self._archive.support_concurrent_extractions \
                   and not self._archive.is_solid():
                    max_threads = prefs['max extract threads']
                else:
                    max_threads = 1
                self._max_threads = max_threads
                if self._archive.is_solid():
                    fn = self._extract_all_files
                else:
                    fn = self._extract_file
                self._extract_thread = WorkerThread(fn,
                                                    name='extract',
                                                    max_threads=max_threads,
                                                    unique_orders=True)
                self._extract_started = True
            else:
                self._extract_thread.clear_orders()
            if self._archive.is_solid():
                # Sort files so we don't queue the same batch multiple times.
                self._extract_thread.append_order(sorted(self._files))
            else:
                self._extract_thread.extend_orders(self._files)

    @callback.Callback
    def contents_listed(self, extractor, files):
        """ Called after the contents of the archive has been listed. """
        pass

    @callback.Callback
    def file_extracted(self, extractor, name, extracted_name):
        """ Called whenever a new file is extracted and ready. """
        pass

    def close(self):
        """Close any open file objects, need only be called manually if the
        extract() method isn't called.
        """
        self.stop()
        if self._archive:
            self._archive.close()

    def _extraction_finished(self, name, extracted_name):
        with self._condition:
            self._files.remove((name, extracted_name))
            self._extracted.add(name)
            self._condition.notifyAll()
            if 0 == len(self._files):
                print 'extracted %u files from %s [%s/%s] in %.3f seconds using %u thread(s) and %s' % (
                    len(self._extracted),
                    self._archive.archive,
                    'solid' if self._archive.is_solid() else 'normal',
                    'clear' if self._archive._password is None else 'encrypted',
                    time.time() - self._start_time,
                    self._max_threads,
                    self._archive._main_archive,
                )
        self.file_extracted(self, name, extracted_name)

    def _extract_all_files(self, files):

        # With multiple extractions for each pass, some of the files might have
        # already been extracted.
        with self._condition:
            files = [(name, extracted_name)
                     for name, extracted_name in files
                     if name not in self._extracted]

        log.debug(u'Extracting from "%s" to "%s": "%s"', self._src, self._dst,
                  ' '.join(['"%s":"%s"' % (name, extracted_name)
                            for name, extracted_name in files]))

        entries = {}
        for name, extracted_name in files:
            entries[name] = os.path.join(self._dst, extracted_name)

        try:
            for name in self._archive.iter_extract(entries):
                if self._extract_thread.must_stop():
                    return
                extracted_name = os.path.basename(entries[name])
                self._extraction_finished(name, extracted_name)

        except Exception, ex:
            # Better to ignore any failed extractions (e.g. from a corrupt
            # archive) than to crash here and leave the main thread in a
            # possible infinite block. Damaged or missing files *should* be
            # handled gracefully by the main program anyway.
            log.error(_('! Extraction error: %s'), ex)
            log.debug('Traceback:\n%s', traceback.format_exc())

    def _extract_file(self, file):
        """Extract the file named <name> to the destination directory,
        mark the file as "ready", then signal a notify() on the Condition
        returned by setup().
        """

        name, extracted_name = file

        log.debug(u'Extracting from "%s" to "%s": "%s":"%s"',
                  self._src, self._dst, name, extracted_name)

        destination_path = os.path.join(self._dst, extracted_name)

        try:
            self._archive.extract(name, destination_path)

        except Exception, ex:
            # Better to ignore any failed extractions (e.g. from a corrupt
            # archive) than to crash here and leave the main thread in a
            # possible infinite block. Damaged or missing files *should* be
            # handled gracefully by the main program anyway.
            log.error(_('! Extraction error: %s'), ex)
            log.debug('Traceback:\n%s', traceback.format_exc())

        if self._extract_thread.must_stop():
            return
        self._extraction_finished(name, extracted_name)

    def _list_contents(self, archive):
        files = []
        for f in archive.iter_contents():
            if self._list_thread.must_stop():
                return
            files.append(f)
        with self._condition:
            self._contents = files
            self._contents_listed = True
        self.contents_listed(self, files)

class ArchiveException(Exception):
    """ Indicate error during extraction operations. """
    pass

# vim: expandtab:sw=4:ts=4
