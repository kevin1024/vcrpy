from vcr.stubs import VCRHTTPSConnection


class TestVCRConnection(object):

    def test_setting_of_attributes_get_propogated_to_real_connection(self):
        vcr_connection = VCRHTTPSConnection('www.examplehost.com')
        vcr_connection.ssl_version = 'example_ssl_version'
        assert vcr_connection.real_connection.ssl_version == 'example_ssl_version'
