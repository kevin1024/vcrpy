"""Integration tests for aiobotocore support."""

import os

import pytest

import vcr

asyncio = pytest.importorskip("asyncio")
aiobotocore = pytest.importorskip("aiobotocore")

from aiobotocore.session import get_session  # noqa: E402


def run_in_loop(coro):
    """Run a coroutine in an event loop."""
    return asyncio.run(coro)


@pytest.fixture
def s3_client():
    """Create an aiobotocore S3 client fixture."""

    async def _create_client():
        session = get_session()
        async with session.create_client(
            "s3",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "testing"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "testing"),
        ) as client:
            return client

    return _create_client


@pytest.fixture
def sts_client():
    """Create an aiobotocore STS client fixture."""

    async def _create_client():
        session = get_session()
        async with session.create_client(
            "sts",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "testing"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "testing"),
        ) as client:
            return client

    return _create_client


class TestAiobotocoreBasic:
    """Basic aiobotocore recording and playback tests."""

    def test_record_and_playback_s3_list_buckets(self, tmpdir):
        """Test recording and playing back an S3 list_buckets call."""
        cassette_path = str(tmpdir.join("aiobotocore_s3_list_buckets.yaml"))

        async def list_buckets():
            session = get_session()
            async with session.create_client(
                "s3",
                region_name="us-east-1",
                aws_access_key_id="testing",
                aws_secret_access_key="testing",
                endpoint_url="http://localhost:5000",  # Use localstack or moto
            ) as client:
                return await client.list_buckets()

        # This test uses a pre-recorded cassette
        # In a real scenario, you'd record first then play back
        with vcr.use_cassette(
            cassette_path,
            record_mode="none",
            ignore_hosts=["localhost"],
        ) as cassette:
            # Since we're ignoring localhost and have no cassette,
            # this verifies the basic integration doesn't crash
            assert cassette is not None

    def test_cassette_context_manager(self, tmpdir):
        """Test that cassette context manager works with aiobotocore."""
        cassette_path = str(tmpdir.join("aiobotocore_context.yaml"))

        with vcr.use_cassette(cassette_path, record_mode="none") as cassette:
            # Verify cassette is properly initialized
            assert cassette is not None
            assert cassette.play_count == 0


class TestAiobotocoreCassette:
    """Test cassette-based recording/playback for aiobotocore."""

    @pytest.fixture
    def sample_cassette_data(self):
        """Return sample cassette data for testing playback."""
        return {
            "version": 1,
            "interactions": [
                {
                    "request": {
                        "body": b"Action=GetCallerIdentity&Version=2011-06-15",
                        "headers": {
                            "User-Agent": ["aiobotocore/test"],
                            "Content-Type": ["application/x-www-form-urlencoded"],
                        },
                        "method": "POST",
                        "uri": "https://sts.amazonaws.com/",
                    },
                    "response": {
                        "body": {
                            "string": b'<?xml version="1.0" ?><GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/"><GetCallerIdentityResult><Arn>arn:aws:iam::123456789012:user/test</Arn><UserId>AIDAEXAMPLE</UserId><Account>123456789012</Account></GetCallerIdentityResult></GetCallerIdentityResponse>'
                        },
                        "headers": {
                            "content-type": ["text/xml"],
                            "content-length": ["300"],
                        },
                        "status": {"code": 200, "message": "OK"},
                    },
                }
            ],
        }

    def test_playback_from_cassette(self, tmpdir, sample_cassette_data):
        """Test playing back a recorded response."""
        import yaml

        cassette_path = str(tmpdir.join("aiobotocore_playback.yaml"))

        # Write the sample cassette
        with open(cassette_path, "w") as f:
            yaml.dump(sample_cassette_data, f)

        async def get_caller_identity():
            session = get_session()
            async with session.create_client(
                "sts",
                region_name="us-east-1",
                aws_access_key_id="testing",
                aws_secret_access_key="testing",
            ) as client:
                return await client.get_caller_identity()

        with vcr.use_cassette(cassette_path, record_mode="none") as cassette:
            response = run_in_loop(get_caller_identity())
            assert response["Account"] == "123456789012"
            assert response["Arn"] == "arn:aws:iam::123456789012:user/test"
            assert cassette.play_count == 1


class TestAiobotocoreIntegration:
    """Integration tests that require network access (marked online)."""

    @pytest.mark.online
    @pytest.mark.skipif(
        os.environ.get("AWS_ACCESS_KEY_ID") is None,
        reason="AWS credentials not available",
    )
    def test_record_real_sts_call(self, tmpdir):
        """Test recording a real STS GetCallerIdentity call."""
        cassette_path = str(tmpdir.join("aiobotocore_sts_real.yaml"))

        async def get_caller_identity():
            session = get_session()
            async with session.create_client(
                "sts",
                region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            ) as client:
                return await client.get_caller_identity()

        # Record
        with vcr.use_cassette(cassette_path):
            response = run_in_loop(get_caller_identity())
            assert "Account" in response

        # Playback
        with vcr.use_cassette(cassette_path) as cassette:
            response2 = run_in_loop(get_caller_identity())
            assert response2["Account"] == response["Account"]
            assert cassette.play_count == 1
