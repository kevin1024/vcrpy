import pytest
import os

boto3 = pytest.importorskip("boto3")

import boto3  # NOQA
import botocore  # NOQA
import vcr  # NOQA

ses = boto3.Session(
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    aws_session_token=None,
    region_name=os.environ['AWS_DEFAULT_REGION'],
    # botocore_session=None,
    # profile_name=None
)

IAM_CLIENT = ses.client('iam')

try:
    from botocore import awsrequest  # NOQA

    botocore_awsrequest = True
except ImportError:
    botocore_awsrequest = False


# skip tests if boto does not use vendored requests anymore
# https://github.com/boto/botocore/pull/1495
boto3_skip_vendored_requests = pytest.mark.skipif(
    botocore_awsrequest,
    reason='botocore version {ver} does not use vendored requests anymore.'.format(
        ver=botocore.__version__))

boto3_skip_awsrequest = pytest.mark.skipif(
    not botocore_awsrequest,
    reason='botocore version {ver} still uses vendored requests.'.format(
        ver=botocore.__version__))


@boto3_skip_vendored_requests
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


@boto3_skip_awsrequest
def test_boto3_awsrequest_stubs(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('boto3-stubs.yml'))):
        from botocore.awsrequest import AWSHTTPConnection, AWSHTTPSConnection
        from vcr.stubs.boto3_stubs import VCRRequestsHTTPConnection, VCRRequestsHTTPSConnection
        assert issubclass(VCRRequestsHTTPConnection, AWSHTTPConnection)
        assert issubclass(VCRRequestsHTTPSConnection, AWSHTTPSConnection)
        AWSHTTPConnection('hostname.does.not.matter')
        AWSHTTPSConnection('hostname.does.not.matter')


def test_boto3_without_vcr():
    username = 'user'
    response = IAM_CLIENT.get_user(UserName=username)

    assert response['User']['UserName'] == username


def test_boto_medium_difficulty(tmpdir):
    username = 'user'

    with vcr.use_cassette(str(tmpdir.join('boto3-medium.yml'))):
        response = IAM_CLIENT.get_user(UserName=username)
        assert response['User']['UserName'] == username

    with vcr.use_cassette(str(tmpdir.join('boto3-medium.yml'))) as cass:
        response = IAM_CLIENT.get_user(UserName=username)
        assert response['User']['UserName'] == username
        assert cass.all_played


def test_boto_hardcore_mode(tmpdir):
    username = 'user'
    with vcr.use_cassette(str(tmpdir.join('boto3-hardcore.yml'))):
        ses = boto3.Session(
            aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
            region_name=os.environ['AWS_DEFAULT_REGION'],
        )

        iam_client = ses.client('iam')
        response = iam_client.get_user(UserName=username)
        assert response['User']['UserName'] == username

    with vcr.use_cassette(str(tmpdir.join('boto3-hardcore.yml'))) as cass:
        ses = boto3.Session(
            aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
            aws_session_token=None,
            region_name=os.environ['AWS_DEFAULT_REGION'],
        )

        iam_client = ses.client('iam')
        response = iam_client.get_user(UserName=username)
        assert response['User']['UserName'] == username
        assert cass.all_played
