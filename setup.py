#!/usr/bin/env python

import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)

setup(name='vcrpy',
      version='0.0.3',
      description="A Python port of Ruby's VCR to make mocking HTTP easier",
      author='Kevin McCarthy',
      author_email='me@kevinmccarthy.org',
      url='https://github.com/kevin1024/vcrpy',
      packages=['vcr'],
      install_requires=['PyYAML'],
      license='MIT',
      tests_require=['pytest'],
      cmdclass={'test': PyTest},
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Programming Language :: Python',
          'Topic :: Software Development :: Testing',
          'Topic :: Internet :: WWW/HTTP',
          'License :: OSI Approved :: MIT License',
      ],
)
