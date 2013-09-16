import re

pattern = r"multipart/[^;]*;\s*boundary=(.*)"
constant_boundary_string = "ffeac16b6e044eec98d4176a95e68663-"


def replace_multipart_boundaries_with_constant(header, body):
    """
    TODO Does not account for boundaries that span multiple lines
    """
    def replace_all(text, dic):
        for i, j in dic.iteritems():
            text = text.replace(i, j)
        return text

    def strip_quotes(string):
        if string.startswith('"') and string.endswith('"'):
            string = string[1:-1]
        return string

    # Find the exact capitalisation of 'Content-Type' in the header dictionary and access that
    ct = next((x for x in header if x.lower() == 'content-type'), None)
    if ct:
        header_boundary_possibly_with_quotes = re.search(pattern, header[ct]).group(1)
        if header_boundary_possibly_with_quotes:
            boundaries = [strip_quotes(header_boundary_possibly_with_quotes)]
            body_boundaries = [strip_quotes(x) for x in re.findall(pattern, body)]
            boundaries.extend(body_boundaries)
            replacements = {b: constant_boundary_string + str(idx) for (b, idx) in
                            zip(boundaries, range(0, len(boundaries)))}
            header[ct] = replace_all(header[ct], replacements)
            body = replace_all(body, replacements)
    return header, body


class Request(object):
    def __init__(self, protocol, host, port, method, path, body, headers):
        # Compute a multipart-boundary agnostic body and headers; use these instead.
        header, self.body = replace_multipart_boundaries_with_constant(headers, body)
        self.protocol = protocol
        self.host = host
        self.port = port
        self.method = method
        self.path = path
        # make headers a frozenset so it will be hashable
        self.headers = frozenset(headers.items())

    @property
    def url(self):
        return "{0}://{1}{2}".format(self.protocol, self.host, self.path)

    def __key(self):
        return (
            self.host,
            self.port,
            self.method,
            self.path,
            self.body,
            self.headers
        )

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __str__(self):
        return "<Request ({0}) {1}>".format(self.method, self.url)

    def __repr__(self):
        return self.__str__()

    def _to_dict(self):
        return {
            'protocol': self.protocol,
            'host': self.host,
            'port': self.port,
            'method': self.method,
            'path': self.path,
            'body': self.body,
            'headers': self.headers,
        }

    @classmethod
    def _from_dict(cls, dct):
        return Request(**dct)
