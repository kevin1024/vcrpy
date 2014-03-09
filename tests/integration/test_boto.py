import pytest
boto = pytest.importorskip("boto")
from boto.s3.connection import S3Connection
from boto.s3.key import Key
import vcr

def test_boto_without_vcr():
    s3_conn = S3Connection()
    s3_bucket = s3_conn.get_bucket('boto-demo-1394171994') # a bucket you can access
    k = Key(s3_bucket)
    k.key = 'test.txt'
    k.set_contents_from_string('hello world i am a string')

def test_boto_medium_difficulty(tmpdir):
    s3_conn = S3Connection()
    s3_bucket = s3_conn.get_bucket('boto-demo-1394171994') # a bucket you can access
    with vcr.use_cassette(str(tmpdir.join('boto-medium.yml'))) as cass:
        k = Key(s3_bucket)
        k.key = 'test.txt'
        k.set_contents_from_string('hello world i am a string')

    with vcr.use_cassette(str(tmpdir.join('boto-medium.yml'))) as cass:
        k = Key(s3_bucket)
        k.key = 'test.txt'
        k.set_contents_from_string('hello world i am a string')


def test_boto_hardcore_mode(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('boto-hardcore.yml'))) as cass:
        s3_conn = S3Connection()
        s3_bucket = s3_conn.get_bucket('boto-demo-1394171994') # a bucket you can access
        k = Key(s3_bucket)
        k.key = 'test.txt'
        k.set_contents_from_string('hello world i am a string')

    with vcr.use_cassette(str(tmpdir.join('boto-hardcore.yml'))) as cass:
        s3_conn = S3Connection()
        s3_bucket = s3_conn.get_bucket('boto-demo-1394171994') # a bucket you can access
        k = Key(s3_bucket)
        k.key = 'test.txt'
        k.set_contents_from_string('hello world i am a string')
