import mock
import pytest

from vcr import VCR, use_cassette
from vcr.request import Request
from vcr.stubs import VCRHTTPSConnection


def test_vcr_use_cassette():
    record_mode = mock.Mock()
    test_vcr = VCR(record_mode=record_mode)
    with mock.patch('vcr.cassette.Cassette.load', return_value=mock.MagicMock(inject=False)) as mock_cassette_load:
        @test_vcr.use_cassette('test')
        def function():
            pass
        assert mock_cassette_load.call_count == 0
        function()
        assert mock_cassette_load.call_args[1]['record_mode'] is record_mode

        # Make sure that calls to function now use cassettes with the
        # new filter_header_settings
        test_vcr.record_mode = mock.Mock()
        function()
        assert mock_cassette_load.call_args[1]['record_mode'] == test_vcr.record_mode

        # Ensure that explicitly provided arguments still supercede
        # those on the vcr.
        new_record_mode = mock.Mock()

    with test_vcr.use_cassette('test', record_mode=new_record_mode) as cassette:
        assert cassette.record_mode == new_record_mode


def test_vcr_before_record_request_params():
    base_path = 'http://httpbin.org/'
    def before_record_cb(request):
        if request.path != '/get':
            return request
    test_vcr = VCR(filter_headers=('cookie',), before_record_request=before_record_cb,
                   ignore_hosts=('www.test.com',), ignore_localhost=True,
                   filter_query_parameters=('foo',))

    with test_vcr.use_cassette('test') as cassette:
        assert cassette.filter_request(Request('GET', base_path + 'get', '', {})) is None
        assert cassette.filter_request(Request('GET', base_path + 'get2', '', {})) is not None

        assert cassette.filter_request(Request('GET', base_path + '?foo=bar', '', {})).query == []
        assert cassette.filter_request(
            Request('GET', base_path + '?foo=bar', '',
                    {'cookie': 'test', 'other': 'fun'})).headers == {'other': 'fun'}
        assert cassette.filter_request(Request('GET', base_path + '?foo=bar', '',
                                               {'cookie': 'test', 'other': 'fun'})).headers == {'other': 'fun'}

        assert cassette.filter_request(Request('GET', 'http://www.test.com' + '?foo=bar', '',
                                               {'cookie': 'test', 'other': 'fun'})) is None

    with test_vcr.use_cassette('test', before_record_request=None) as cassette:
        # Test that before_record can be overwritten with
        assert cassette.filter_request(Request('GET', base_path + 'get', '', {})) is not None


@pytest.fixture
def random_fixture():
    return 1


@use_cassette('test')
def test_fixtures_with_use_cassette(random_fixture):
    # Applying a decorator to a test function that requests features can cause
    # problems if the decorator does not preserve the signature of the original
    # test function.

    # This test ensures that use_cassette preserves the signature of
    # the original test function, and thus that use_cassette is
    # compatible with py.test fixtures. It is admittedly a bit strange
    # because the test would never even run if the relevant feature
    # were broken.
    pass


def test_custom_patchers():
    class Test(object):
        attribute = None
        attribute2 = None
    test_vcr = VCR(custom_patches=((Test, 'attribute', VCRHTTPSConnection),))
    with test_vcr.use_cassette('custom_patches'):
        assert issubclass(Test.attribute, VCRHTTPSConnection)
        assert VCRHTTPSConnection is not Test.attribute

    with test_vcr.use_cassette('custom_patches', custom_patches=((Test, 'attribute2', VCRHTTPSConnection),)):
        assert issubclass(Test.attribute, VCRHTTPSConnection)
        assert VCRHTTPSConnection is not Test.attribute
        assert Test.attribute is Test.attribute2


def test_inject_cassette():
    vcr = VCR(inject_cassette=True)
    @vcr.use_cassette('test', record_mode='once')
    def with_cassette_injected(cassette):
        assert cassette.record_mode == 'once'

    @vcr.use_cassette('test', record_mode='once', inject_cassette=False)
    def without_cassette_injected():
        pass

    with_cassette_injected()
    without_cassette_injected()


def test_with_current_defaults():
    vcr = VCR(inject_cassette=True, record_mode='once')
    @vcr.use_cassette('test', with_current_defaults=False)
    def changing_defaults(cassette, checks):
        checks(cassette)
    @vcr.use_cassette('test', with_current_defaults=True)
    def current_defaults(cassette, checks):
        checks(cassette)

    def assert_record_mode_once(cassette):
        assert cassette.record_mode == 'once'

    def assert_record_mode_all(cassette):
        assert cassette.record_mode == 'all'

    changing_defaults(assert_record_mode_once)
    current_defaults(assert_record_mode_once)

    vcr.record_mode = 'all'
    changing_defaults(assert_record_mode_all)
    current_defaults(assert_record_mode_once)
