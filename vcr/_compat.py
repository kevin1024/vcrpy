try:
    import httplib
    from urllib2 import urlopen
    from urllib import urlencode
except ImportError:
    import http.client as httplib
    from urllib.request import urlopen
    from urllib.parse import urlencode

