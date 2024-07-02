import contextlib
import http.client as httplib
from unittest import mock

from pytest import mark

from vcr import mode, use_cassette
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

    def test_body_consumed_once(self, tmpdir, httpbin):
        testfile = str(tmpdir.join("body_consumed_once.yml"))
        host, port = httpbin.host, httpbin.port
        match_on = ["method", "uri", "body"]
        chunks1 = [b"1234567890"]
        chunks2 = [b"9876543210"]
        with use_cassette(testfile, match_on=match_on):
            conn1 = httplib.HTTPConnection(host, port)
            conn1.request("POST", "/anything", body=iter(chunks1))
            resp1 = conn1.getresponse()
            assert resp1.status == 501  # Chunked request Not implemented
            conn2 = httplib.HTTPConnection(host, port)
            conn2.request("POST", "/anything", body=iter(chunks2))
            resp2 = conn2.getresponse()
            assert resp2.status == 501  # Chunked request Not implemented
        with use_cassette(testfile, match_on=match_on) as cass:
            conn2 = httplib.HTTPConnection(host, port)
            conn2.request("POST", "/anything", body=iter(chunks2))
            resp2 = conn2.getresponse()
            assert resp2.status == 501  # Chunked request Not implemented
            assert cass.play_counts[0] == 0
            assert cass.play_counts[1] == 1
