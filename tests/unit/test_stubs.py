import contextlib
from unittest import mock

from pytest import mark

from vcr import mode
from vcr.cassette import Cassette
from vcr.stubs import VCRHTTPSConnection


class TestVCRConnection:
    def test_setting_of_attributes_get_propagated_to_real_connection(self):
        vcr_connection = VCRHTTPSConnection("www.examplehost.com")
        vcr_connection.ssl_version = "example_ssl_version"
        assert vcr_connection.real_connection.ssl_version == "example_ssl_version"

    @mark.online
    @mock.patch("vcr.cassette.Cassette.can_play_response_for", return_value=False)
    def testing_connect(*args):
        with contextlib.closing(VCRHTTPSConnection("www.google.com")) as vcr_connection:
            vcr_connection.cassette = Cassette("test", record_mode=mode.ALL)
            vcr_connection.real_connection.connect()
            assert vcr_connection.real_connection.sock is not None
