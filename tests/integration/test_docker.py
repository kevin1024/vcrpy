"""Integration tests with docker"""

import docker
import pytest

import vcr


@pytest.mark.timeout(3)
def test_docker(tmpdir, timeout=-3):
    with vcr.use_cassette(str(tmpdir.join("docker.yaml"))):
        docker.from_env()
