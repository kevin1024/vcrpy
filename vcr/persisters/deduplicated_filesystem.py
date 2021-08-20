# https://github.com/Azure/azure-sdk-for-python/pull/17973/files

import copy
import os

from vcr.serialize import serialize, deserialize
from .filesystem import FilesystemPersister


ATTRIBUTES_TO_COMPARE = [
    "body",
    "headers",
    "host",
    "method",
    "path",
    "protocol",
    "query",
    "scheme",
    "uri",
    "url",
]


def trim_duplicates(cassette_dict):
    # Dict[str] -> Dict[str]
    cassette_copy = copy.deepcopy(cassette_dict)
    requests = cassette_dict["requests"]
    responses = cassette_dict["responses"]
    pairs_to_remove = []
    for i in range(1, len(requests)):
        for j in range(1, min(i, 4)):
            if same_requests(requests[i - j], requests[i]):
                pairs_to_remove.append(i - j)
    # Always keep the last one
    ret = {"requests": [], "responses": []}

    for i in range(len(requests)):
        if i not in pairs_to_remove:
            ret["requests"].append(requests[i])
            ret["responses"].append(responses[i])

    return ret


def same_requests(request1, request2):
    # (vcr.Request, vcr.Request) -> bool
    for attr in ATTRIBUTES_TO_COMPARE:
        if getattr(request1, attr) != getattr(request2, attr):
            return False

    return True


class DeduplicatedFilesystemPersister(FilesystemPersister):
    @staticmethod
    def save_cassette(cassette_path, cassette_dict, serializer):
        cassette_dict = trim_duplicates(cassette_dict)
        FilesystemPersister.save_cassette(cassette_path, cassette_dict, serializer)
