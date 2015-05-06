#!/usr/bin/env python

import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)

setup(
    name='vcrpy',
    version='1.4.2',
    description=(
        "Automatically mock your HTTP interactions to simplify and "
        "speed up testing"
    ),
    author='Kevin McCarthy',
    author_email='me@kevinmccarthy.org',
    url='https://github.com/kevin1024/vcrpy',
    packages=find_packages(exclude=("tests*",)),
    install_requires=['PyYAML', 'mock', 'six', 'contextlib2',
                      'wrapt', 'backport_collections'],
    license='MIT',
    tests_require=['pytest', 'mock', 'pytest-localserver'],
    cmdclass={'test': PyTest},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Testing',
        'Topic :: Internet :: WWW/HTTP',
        'License :: OSI Approved :: MIT License',
    ]
)
