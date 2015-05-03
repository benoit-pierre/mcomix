# -*- coding: utf-8 -*-
""" file_provider.py - Handles listing files for the current directory and
    switching to the next/previous directory. """

import os
import re

from mcomix import image_tools
from mcomix import archive_tools
from mcomix import tools
from mcomix import constants
from mcomix import preferences
from mcomix import i18n
from mcomix import log

def get_file_provider(filelist):
    """ Initialize a FileProvider with the files in <filelist>.
    If len(filelist) is 1, a OrderedFileProvider will be constructed, which
    will simply open all files in the passed directory.
    If len(filelist) is greater 1, a PreDefinedFileProvider will be created,
    which will only ever list the files that were passed into it.
    If len(filelist) is zero, FileProvider will look at the last file opened,
    if "Auto Open last file" is set. Otherwise, no provider is constructed. """

    if len(filelist) > 0:
        if len(filelist) == 1:
            if os.path.exists(filelist[0]):
                provider = OrderedFileProvider(filelist[0])
            else:
                provider = None
        else:
            provider = PreDefinedFileProvider(filelist)


    elif (preferences.prefs['auto load last file']
        and os.path.isfile(preferences.prefs['path to last file'])):
        provider = OrderedFileProvider(preferences.prefs['path to last file'])

    else:
        provider = None

    return provider

class FileProvider(object):
    """ Base class for various file listing strategies. """

    # Constants for determining which files to list.
    IMAGES, ARCHIVES = 1, 2

    def set_directory(self, file_or_directory):
        pass

    def get_directory(self):
        return os.path.abspath(os.getcwdu())

    def list_files(self, mode=IMAGES):
        return []

    def next_directory(self):
        return False

    def previous_directory(self):
        return False

    @staticmethod
    def sort_files(files):
        """ Sorts a list of C{files} depending on the current preferences.
        The list is sorted in-place. """
        if preferences.prefs['sort by'] == constants.SORT_NAME:
            tools.alphanumeric_sort(files)
        elif preferences.prefs['sort by'] == constants.SORT_LAST_MODIFIED:
            # Most recently modified file first
            files.sort(key=lambda filename: os.path.getmtime(filename)*-1)
        elif preferences.prefs['sort by'] == constants.SORT_SIZE:
            # Smallest file first
            files.sort(key=lambda filename: os.stat(filename).st_size)
        # else: don't sort at all: use OS ordering.

        # Default is ascending.
        if preferences.prefs['sort order'] == constants.SORT_DESCENDING:
            files.reverse()


class OrderedFileProvider(FileProvider):
    """ This provider will list all files in the same directory as the
        one passed to the constructor. """

    def __init__(self, file_or_directory):
        """ Initializes the file listing. If <file_or_directory> is a file,
            directory will be used as base path. If it is a directory, that
            will be used as base file. """

        self.set_directory(file_or_directory)

    def set_directory(self, file_or_directory):
        """ Sets the base directory. """

        if os.path.isdir(file_or_directory):
            dir = file_or_directory
        elif os.path.isfile(file_or_directory):
            dir = os.path.dirname(file_or_directory)
        else:
            # Passed file doesn't exist
            raise ValueError(_("Invalid path: '%s'") % file_or_directory)

        self.base_dir = os.path.abspath(dir)

    def get_directory(self):
        return self.base_dir

    def list_files(self, mode=FileProvider.IMAGES):
        """ Lists all files in the current directory.
            Returns a list of absolute paths, already sorted. """

        if mode == FileProvider.IMAGES:
            should_accept = image_tools.is_image_file
        elif mode == FileProvider.ARCHIVES:
            should_accept = archive_tools.is_archive_file
        else:
            should_accept = lambda file: True

        try:
            files = [ os.path.join(self.base_dir, filename) for filename in
                      # Explicitly convert all files to Unicode, even when
                      # os.listdir returns a mixture of byte/unicode strings.
                      # (MComix bug #3424405)
                      [ i18n.to_unicode(fn) for fn in os.listdir(self.base_dir) ]
                      if should_accept(os.path.join(self.base_dir, filename)) ]

            FileProvider.sort_files(files)

            return files
        except OSError:
            log.warning(u'! ' + _('Could not open %s: Permission denied.'), self.base_dir)
            return []

    def next_directory(self):
        """ Switches to the next sibling directory. Next call to
            list_file() returns files in the new directory.
            Returns True if the directory was changed, otherwise False. """

        directories = self.__get_sibling_directories(self.base_dir)
        current_index = directories.index(self.base_dir)
        if current_index < len(directories) - 1:
            self.base_dir = directories[current_index + 1]
            return True
        else:
            return False


    def previous_directory(self):
        """ Switches to the previous sibling directory. Next call to
            list_file() returns files in the new directory.
            Returns True if the directory was changed, otherwise False. """

        directories = self.__get_sibling_directories(self.base_dir)
        current_index = directories.index(self.base_dir)
        if current_index > 0:
            self.base_dir = directories[current_index - 1]
            return True
        else:
            return False

    def __get_sibling_directories(self, dir):
        """ Returns a list of all sibling directories of <dir>,
            already sorted. """

        parent_dir = os.path.dirname(dir)
        directories = [ os.path.join(parent_dir, directory)
                for directory in os.listdir(parent_dir)
                if os.path.isdir(os.path.join(parent_dir, directory)) ]

        tools.alphanumeric_sort(directories)
        return directories


class PreDefinedFileProvider(FileProvider):
    """ Returns only a list of files as passed to the constructor. """

    def __init__(self, files):
        """ <files> is a list of files that should be shown. The list is filtered
            to contain either only images, or only archives, depending on what the first
            file is, since FileHandler will probably have problems of archives and images
            are mixed in a file list. """

        should_accept = self.__get_file_filter(files)

        self.__files = [ ]

        for file in files:
            if os.path.isdir(file):
                provider = OrderedFileProvider(file)
                self.__files.extend(provider.list_files())

            elif should_accept(file):
                self.__files.append(os.path.abspath(file))


    def list_files(self, mode=FileProvider.IMAGES):
        """ Returns the files as passed to the constructor. """

        return self.__files

    def __get_file_filter(self, files):
        """ Determines what kind of files should be filtered in the given list
        of <files>. Returns either a filter accepting only images, or only archives,
        depending on what type of file is found first in the list. """

        for file in files:
            if os.path.isfile(file):
                if image_tools.is_image_file(file):
                    return image_tools.is_image_file
                if archive_tools.is_archive_file(file):
                    return archive_tools.is_archive_file

        # Default filter only accepts images.
        return image_tools.is_image_file


# vim: expandtab:sw=4:ts=4
