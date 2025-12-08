import contextlib
import http.client as httplib
from io import BytesIO
from tempfile import NamedTemporaryFile
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

    def test_body_consumed_once_stream(self, tmpdir, httpbin):
        self._test_body_consumed_once(
            tmpdir,
            httpbin,
            BytesIO(b"1234567890"),
            BytesIO(b"9876543210"),
            BytesIO(b"9876543210"),
        )

    def test_body_consumed_once_iterator(self, tmpdir, httpbin):
        self._test_body_consumed_once(
            tmpdir,
            httpbin,
            iter([b"1234567890"]),
            iter([b"9876543210"]),
            iter([b"9876543210"]),
        )

    # data2 and data3 should serve the same data, potentially as iterators
    def _test_body_consumed_once(
        self,
        tmpdir,
        httpbin,
        data1,
        data2,
        data3,
    ):
        with NamedTemporaryFile(dir=tmpdir, suffix=".yml") as f:
            testpath = f.name
            # NOTE: ``use_cassette`` is not okay with the file existing
            #       already.  So we using ``.close()`` to not only
            #       close but also delete the empty file, before we start.
            f.close()
            host, port = httpbin.host, httpbin.port
            match_on = ["method", "uri", "body"]
            with use_cassette(testpath, match_on=match_on):
                conn1 = httplib.HTTPConnection(host, port)
                conn1.request("POST", "/anything", body=data1)
                conn1.getresponse()
                conn2 = httplib.HTTPConnection(host, port)
                conn2.request("POST", "/anything", body=data2)
                conn2.getresponse()
            with use_cassette(testpath, match_on=match_on) as cass:
                conn3 = httplib.HTTPConnection(host, port)
                conn3.request("POST", "/anything", body=data3)
                conn3.getresponse()
            assert cass.play_counts[0] == 0
            assert cass.play_counts[1] == 1
