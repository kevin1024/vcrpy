#!/usr/bin/env python

import codecs
import os
import re
from pathlib import Path

from setuptools import find_packages, setup

long_description = Path("README.rst").read_text()
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


install_requires = [
    "PyYAML",
    "wrapt",
]

extras_require = {
    "tests": [
        "aiohttp",
        "boto3",
        "cryptography",
        "httpbin",
        "httpcore",
        "httplib2",
        "httpx",
        "pycurl; platform_python_implementation !='PyPy'",
        "pytest",
        "pytest-aiohttp",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-httpbin",
        "requests>=2.22.0",
        "tornado",
        "urllib3",
        "werkzeug==2.0.3",
    ],
}

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
    python_requires=">=3.10",
    install_requires=install_requires,
    license="MIT",
    extras_require=extras_require,
    tests_require=extras_require["tests"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Testing",
        "Topic :: Internet :: WWW/HTTP",
        "License :: OSI Approved :: MIT License",
    ],
)
