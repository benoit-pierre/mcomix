#!/usr/bin/env python2

from __future__ import print_function

import os
import sys
import subprocess

arch = '32'
runtime = '9'
pyversion = '2.7'

class PyGObjectInstaller(object):

    def __init__(self, srcdir, dstdir, verbose=False):
        self.srcdir = srcdir
        self.dstdir = dstdir
        self._verbose = verbose

    def get_package_directories(self, package):
        format_args = {
            'arch': arch,
            'package': package,
            'runtime': runtime,
            'srcdir': self.srcdir,
        }
        datadir = '%(srcdir)s/noarch/%(package)s' % format_args
        bindir = '%(srcdir)s/rtvc%(runtime)s-%(arch)s/%(package)s' % format_args
        return datadir, bindir

    def get_package_dependencies(self, package):
        datadir, bindir = self.get_package_directories(package)
        depends = '%s/depends.txt' % datadir
        if not os.path.exists(depends):
            return set()
        with open(depends, 'r') as fp:
            dependencies = set(fp.read().split())
        for sub_package in tuple(dependencies):
            dependencies.update(self.get_package_dependencies(sub_package))
        return dependencies

    def install_archive(self, archive):
        cmd = ['7z', 'x', '-o%s' % self.dstdir, '-y', archive]
        if self._verbose:
            print(' '.join(cmd))
        with open(os.devnull, 'wb') as null:
            subprocess.check_call(cmd, stdout=null)

    def install_package(self, package):
        datadir, bindir = self.get_package_directories(package)
        self.install_archive('%s/%s.data.7z' % (datadir, package))
        self.install_archive('%s/%s.bin.7z' % (bindir, package))

    def install_binding(self, ):
        archive = '%(srcdir)s/binding/py%(pyversion)s-%(arch)s/py%(pyversion)s-%(arch)s.7z' % {
            'arch': arch,
            'srcdir': self.srcdir,
            'pyversion': pyversion,
        }
        self.install_archive(archive)

    def install(self, package_list, verbose=False):

        package_list = set(package_list)

        for package in tuple(package_list):
            package_list.update(self.get_package_dependencies(package))

        package_list = ['Base'] + sorted(package_list)

        print('installing package(s): %s' % ' '.join(package_list))

        self.install_binding()

        for package in package_list:
            self.install_package(package)

if '__main__' == __name__:
    srcdir = sys.argv[1]
    dstdir = sys.argv[2]
    package_list = set(sys.argv[3:])
    installer = PyGObjectInstaller(srcdir, dstdir)
    installer.install(package_list)

