import pytest

boto3 = pytest.importorskip("boto3")

import boto3  # NOQA
import botocore  # NOQA
import vcr  # NOQA

try:
    from botocore import awsrequest

    botocore_awsrequest = True
    botocore_vendored_requests = False
except ImportError:
    botocore_awsrequest = False
    botocore_vendored_requests = True

# skip tests if boto does not use vendored requests anymore
# https://github.com/boto/botocore/pull/1495
boto3_vendored = pytest.mark.skipif(
    botocore_vendored_requests,
    reason='botocore version {ver} does not use vendored requests anymore.'.format(
        ver=botocore.__version__))

boto3_awsrequest = pytest.mark.skipif(
    botocore_awsrequest,
    reason='botocore version {ver} still uses vendored requests.'.format(
        ver=botocore.__version__))

bucket = 'boto3-demo-1337'  # a bucket you can access
key = 'test/my_test.txt'  # key with r+w access
content = 'hello world i am a string'  # content to put in the test file


@boto3_awsrequest
def test_boto_vendored_stubs(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('boto3-stubs.yml'))):
        # Perform the imports within the patched context so that
        # HTTPConnection, VerifiedHTTPSConnection refers to the patched version.
        from botocore.vendored.requests.packages.urllib3.connectionpool import \
            HTTPConnection, VerifiedHTTPSConnection
        from vcr.stubs.boto3_stubs import VCRRequestsHTTPConnection, VCRRequestsHTTPSConnection
        # Prove that the class was patched by the stub and that we can instantiate it.
        assert issubclass(HTTPConnection, VCRRequestsHTTPConnection)
        assert issubclass(VerifiedHTTPSConnection, VCRRequestsHTTPSConnection)
        HTTPConnection('hostname.does.not.matter')
        VerifiedHTTPSConnection('hostname.does.not.matter')


@boto3_vendored
def test_boto3_awsrequest_stubs(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('boto3-stubs.yml'))):
        from botocore.awsrequest import AWSHTTPConnection, AWSHTTPSConnection
        from vcr.stubs.boto3_stubs import VCRRequestsHTTPConnection, VCRRequestsHTTPSConnection
        # addopted from test_boto_vendored_stubs, but
        # Todo this seems to be other way around
        assert issubclass(AWSHTTPConnection, VCRRequestsHTTPConnection)
        assert issubclass(AWSHTTPSConnection, VCRRequestsHTTPSConnection)
        AWSHTTPConnection('hostname.does.not.matter')
        AWSHTTPSConnection('hostname.does.not.matter')


def test_boto3_without_vcr():
    s3_resource = boto3.resource('s3')
    b = s3_resource.Bucket(bucket)
    b.put_object(Key=key, Body=content)

    # retrieve content to check it
    o = s3_resource.Object(bucket, key).get()

    # decode for python3
    assert content == o['Body'].read().decode('utf-8')


def test_boto_medium_difficulty(tmpdir):
    s3_resource = boto3.resource('s3')
    b = s3_resource.Bucket(bucket)
    with vcr.use_cassette(str(tmpdir.join('boto3-medium.yml'))):
        b.put_object(Key=key, Body=content)
        o = s3_resource.Object(bucket, key).get()
        assert content == o['Body'].read().decode('utf-8')

    with vcr.use_cassette(str(tmpdir.join('boto3-medium.yml'))) as cass:
        b.put_object(Key=key, Body=content)
        o = s3_resource.Object(bucket, key).get()
        assert content == o['Body'].read().decode('utf-8')
        assert cass.all_played


def test_boto_hardcore_mode(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('boto3-hardcore.yml'))):
        s3_resource = boto3.resource('s3')
        b = s3_resource.Bucket(bucket)
        b.put_object(Key=key, Body=content)
        o = s3_resource.Object(bucket, key).get()
        assert content == o['Body'].read().decode('utf-8')

    with vcr.use_cassette(str(tmpdir.join('boto3-hardcore.yml'))) as cass:
        s3_resource = boto3.resource('s3')
        b = s3_resource.Bucket(bucket)
        b.put_object(Key=key, Body=content)
        o = s3_resource.Object(bucket, key).get()
        assert content == o['Body'].read().decode('utf-8')
        assert cass.all_played
