'''Basic tests about save behavior'''
# coding=utf-8

# External imports
import os
import urllib2

# Internal imports
import vcr

def test_disk_saver_nowrite(tmpdir):
    '''Ensure that when you close a cassette without changing it it doesn't rewrite the file'''
    fname = str(tmpdir.join('synopsis.yaml'))
    with vcr.use_cassette(fname) as cass:
        urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 0
    last_mod = os.path.getmtime(fname)

    with vcr.use_cassette(fname) as cass:
        urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 1
        assert cass.dirty == False
    last_mod2 = os.path.getmtime(fname)

    assert last_mod == last_mod2

def test_disk_saver_write(tmpdir):
    '''Ensure that when you close a cassette with changing it it does rewrite the file'''
    fname = str(tmpdir.join('synopsis.yaml'))
    with vcr.use_cassette(fname) as cass:
        urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 0
    last_mod = os.path.getmtime(fname)

    with vcr.use_cassette(fname) as cass:
        urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        urllib2.urlopen('http://httpbin.org/').read()
        assert cass.play_count == 1
        assert cass.dirty
    last_mod2 = os.path.getmtime(fname)

    assert last_mod != last_mod2

