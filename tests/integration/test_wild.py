import pytest
requests = pytest.importorskip("requests")

import vcr

def test_domain_redirect():
    '''Ensure that redirects across domains are considered unique'''
    # In this example, seomoz.org redirects to moz.com, and if those
    # requests are considered identical, then we'll be stuck in a redirect
    # loop.
    url = 'http://seomoz.org/'
    with vcr.use_cassette('domain_redirect.yaml') as cass:
        requests.get(url, headers={'User-Agent': 'vcrpy-test'})
        # Ensure that we've now served two responses. One for the original
        # redirect, and a second for the actual fetch
        assert len(cass) == 2

