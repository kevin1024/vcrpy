# .. _persister_example:

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..serialize import deserialize, serialize

if TYPE_CHECKING:
    from ..types import CassetteDict, LoadedCassette, Serializer, StrPath


class CassetteNotFoundError(FileNotFoundError):
    pass


class CassetteDecodeError(ValueError):
    pass


class FilesystemPersister:
    @classmethod
    def load_cassette(cls, cassette_path: StrPath, serializer: Serializer) -> LoadedCassette:
        path = Path(cassette_path)  # if cassette path is already Path this is no operation
        if not path.is_file():
            raise CassetteNotFoundError()
        try:
            with path.open() as f:
                data = f.read()
        except UnicodeDecodeError as err:
            raise CassetteDecodeError("Can't read Cassette, Encoding is broken") from err

        if not data.strip():
            # An empty file is treated like a missing cassette and recorded again, as in Ruby VCR.
            raise CassetteNotFoundError()

        return deserialize(data, serializer)

    @staticmethod
    def save_cassette(cassette_path: StrPath, cassette_dict: CassetteDict, serializer: Serializer) -> None:
        data = serialize(cassette_dict, serializer)
        path = Path(cassette_path)  # if cassette path is already Path this is no operation

        cassette_folder = path.parent
        if not cassette_folder.exists():
            cassette_folder.mkdir(parents=True)

        with path.open("w") as f:
            f.write(data)
