#!/usr/bin/env python

import codecs
import os
import re
import sys

from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

long_description = open("README.rst").read()
here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    # intentionally *not* adding an encoding option to open, See:
    #   https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    with codecs.open(os.path.join(here, *parts), "r") as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)

    raise RuntimeError("Unable to find version string.")


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
    "PyYAML",
    "wrapt",
    "yarl",
    # Support for urllib3 >=2 needs Python >=3.10
    # so we need to block urllib3 >=2 for Python <3.10 for now.
    # Note that vcrpy would work fine without any urllib3 around,
    # so this block and the dependency can be dropped at some point
    # in the future. For more Details:
    # https://github.com/kevin1024/vcrpy/pull/699#issuecomment-1551439663
    "urllib3 <2; python_version <'3.10'",
]

tests_require = [
    "aiohttp",
    "boto3",
    "httplib2",
    "httpx",
    "pytest",
    "pytest-aiohttp",
    "pytest-httpbin",
    "requests>=2.16.2",
    "tornado",
    # Needed to un-break httpbin 0.7.0. For httpbin >=0.7.1 and after,
    # this pin and the dependency itself can be removed, provided
    # that the related bug in httpbin has been fixed:
    # https://github.com/kevin1024/vcrpy/issues/645#issuecomment-1562489489
    # https://github.com/postmanlabs/httpbin/issues/673
    # https://github.com/postmanlabs/httpbin/pull/674
    "Werkzeug==2.0.3",
]

setup(
    name="vcrpy",
    version=find_version("vcr", "__init__.py"),
    description=("Automatically mock your HTTP interactions to simplify and speed up testing"),
    long_description=long_description,
    long_description_content_type="text/x-rst",
    author="Kevin McCarthy",
    author_email="me@kevinmccarthy.org",
    url="https://github.com/kevin1024/vcrpy",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.9",
    install_requires=install_requires,
    license="MIT",
    tests_require=tests_require,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Testing",
        "Topic :: Internet :: WWW/HTTP",
        "License :: OSI Approved :: MIT License",
    ],
)
