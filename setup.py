#!/usr/bin/env python

import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

long_description = open('README.rst', 'r').read()

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
    version='1.6.0',
    description=(
        "Automatically mock your HTTP interactions to simplify and "
        "speed up testing"
    ),
    long_description=long_description,
    author='Kevin McCarthy',
    author_email='me@kevinmccarthy.org',
    url='https://github.com/kevin1024/vcrpy',
    packages=find_packages(exclude=("tests*",)),
    install_requires=['PyYAML', 'wrapt', 'six>=1.5'],
    extras_require = {
        ':python_version in "2.4, 2.5, 2.6"':
            ['contextlib2', 'backport_collections', 'mock'],
        ':python_version in "2.7, 3.1, 3.2"': ['contextlib2', 'mock'],
    },
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
