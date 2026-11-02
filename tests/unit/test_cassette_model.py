"""Cassette, checked against a model: a list of interactions and the set of those played."""

# pyright: reportPrivateUsage=false
# The model saves the cassette with Cassette._save, as leaving a cassette context does.

from __future__ import annotations

from typing import ClassVar, TypeAlias

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from vcr import serialize
from vcr.cassette import Cassette
from vcr.errors import UnhandledHTTPRequestError
from vcr.persisters.filesystem import CassetteNotFoundError
from vcr.request import Request
from vcr.serializers import yamlserializer
from vcr.types import CassetteDict, LoadedCassette, Response, Serializer, StrPath

RequestKey: TypeAlias = tuple[str, str]
"""The method and URI of a request."""

# Few distinct requests, so that the cassette holds several that match the same one.
REQUESTS: list[RequestKey] = [
    ("GET", "http://example.com/a"),
    ("GET", "http://example.com/b"),
    ("POST", "http://example.com/a"),
]
requests = st.sampled_from(REQUESTS)


class MemoryPersister:
    """Keeps serialized cassettes in a dict, so saving and loading goes through the serializer."""

    cassettes: ClassVar[dict[StrPath, str]] = {}

    @classmethod
    def load_cassette(cls, cassette_path: StrPath, serializer: Serializer) -> LoadedCassette:
        try:
            return serialize.deserialize(cls.cassettes[cassette_path], serializer)
        except KeyError:
            raise CassetteNotFoundError() from None

    @classmethod
    def save_cassette(
        cls,
        cassette_path: StrPath,
        cassette_dict: CassetteDict,
        serializer: Serializer,
    ) -> None:
        cls.cassettes[cassette_path] = serialize.serialize(cassette_dict, serializer)


def _response(number: int) -> Response:
    return {"status": {"code": 200, "message": "OK"}, "headers": {}, "body": {"string": str(number).encode()}}


class CassetteModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        MemoryPersister.cassettes = {}
        self.cassette = Cassette.load(path="model", persister=MemoryPersister, serializer=yamlserializer)
        # Each request and the response recorded for it
        self.interactions: list[tuple[RequestKey, Response]] = []
        self.played: set[int] = set()  # indices of played interactions
        self.recorded = 0

    def _unplayed(self, key: RequestKey) -> list[int]:
        return [i for i, (k, _) in enumerate(self.interactions) if k == key and i not in self.played]

    @rule(key=requests)
    def append(self, key: RequestKey) -> None:
        self.recorded += 1
        response = _response(self.recorded)
        self.cassette.append(Request(*key, None, {}), response)
        self.interactions.append((key, response))

    @rule(key=requests)
    def play(self, key: RequestKey) -> None:
        unplayed = self._unplayed(key)
        if unplayed:
            assert self.cassette.play_response(Request(*key, None, {})) == self.interactions[unplayed[0]][1]
            self.played.add(unplayed[0])
        else:
            try:
                self.cassette.play_response(Request(*key, None, {}))
            except UnhandledHTTPRequestError:
                pass
            else:
                raise AssertionError("played a response that the model doesn't have")

    @rule()
    def rewind(self) -> None:
        self.cassette.rewind()
        self.played = set()

    @rule()
    def save_and_load(self) -> None:
        self.cassette._save(force=True)
        self.cassette = Cassette.load(path="model", persister=MemoryPersister, serializer=yamlserializer)
        self.played = set()

    @invariant()
    def length(self) -> None:
        assert len(self.cassette) == len(self.interactions)

    @invariant()
    def responses(self) -> None:
        assert self.cassette.responses == [response for _, response in self.interactions]

    @invariant()
    def contains(self) -> None:
        for key in REQUESTS:
            assert (Request(*key, None, {}) in self.cassette) == bool(self._unplayed(key))

    @invariant()
    def play_counts(self) -> None:
        assert self.cassette.play_count == len(self.played)
        assert self.cassette.all_played == (len(self.played) == len(self.interactions))


TestCassetteModel = CassetteModel.TestCase
