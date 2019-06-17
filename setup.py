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


install_requires = [
    'PyYAML',
    'wrapt',
    'six>=1.5',
    'yarl',
]

setup(
    name='vcrpy',
    version='2.1.0',
    description=(
        "Automatically mock your HTTP interactions to simplify and "
        "speed up testing"
    ),
    long_description=long_description,
    author='Kevin McCarthy',
    author_email='me@kevinmccarthy.org',
    url='https://github.com/kevin1024/vcrpy',
    packages=find_packages(exclude=["tests*"]),
    python_requires='>=3.5',
    install_requires=install_requires,
    license='MIT',
    tests_require=['pytest', 'mock', 'pytest-httpbin'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Testing',
        'Topic :: Internet :: WWW/HTTP',
        'License :: OSI Approved :: MIT License',
    ]
)
