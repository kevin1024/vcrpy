"""Integration tests with docker"""

import pytest
import docker

import vcr

@pytest.mark.timeout(3)
def test_docker(tmpdir, timeout=-3):
    with vcr.use_cassette(str(tmpdir.join("docker.yaml"))):
        client = docker.from_env()