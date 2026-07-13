"""Filesystem persister that caches open cassettes"""
import os
from .filesystem import FilesystemPersister

CACHED_CASSETTES = {}


class FilesystemCachedPersister:
    """
    This persister keeps a cache of cassettes, to avoid the overhead of
    serializing and deserializing unchanged cassettes.

    This is especially useful when no changes to the cassette are expected,
    for example when running testsuites with `mode=none`.
    """
    @classmethod
    def load_cassette(cls, cassette_path, serializer):
        """Load a cassette from disk, but cache it for future uses."""
        global CACHED_CASSETTES

        known_cassette = cassette_path in CACHED_CASSETTES
        if known_cassette:
            try:
                cassette_disk_mtime = os.path.getmtime(cassette_path)
            except FileNotFoundError:
                # Simulate FilesystemPersister's behaviour.
                raise ValueError("Cassette not found.")

            # Retrieve cassette's record from the cache.
            cassette_record = CACHED_CASSETTES[cassette_path]

            # Return the cached version if the on-disk cassette has not
            # been modified since we read the cached cassette.
            cassette_cached_mtime = cassette_record["mtime"]
            if cassette_disk_mtime <= cassette_cached_mtime:
                cassette_cached = cassette_record["cassette"]
                return cassette_cached

        # Load cassette from disk if unknown cassette or the on-disk cassette is more recent.
        cassette_from_disk = FilesystemPersister.load_cassette(cassette_path, serializer)

        # Cache cassette for future uses.
        cassette_record = cls._cassette_record_for_cache(cassette_path, cassette_from_disk)
        CACHED_CASSETTES[cassette_path] = cassette_record

        # Return cassette
        return cassette_from_disk

    @staticmethod
    def save_cassette(cassette_path, cassette_dict, serializer):
        """Save a cassette to disk if it has changed since last time it has been saved."""
        global CACHED_CASSETTES

        if cassette_path in CACHED_CASSETTES:
            # Load existing cassette record.
            cassette_record = CACHED_CASSETTES[cassette_path]

            # Do not save anything to disk if there are no new recordings.
            num_recordings_new = len(cassette_dict)
            num_recordings_cached = cassette_record["num_recordings"]
            if num_recordings_new == num_recordings_cached:
                return

        # Save cassette to disk
        FilesystemPersister.save_cassette(cassette_path, cassette_dict, serializer)

        # Cache new version of cassette for future uses.
        cassette_record = FilesystemCachedPersister._cassette_record_for_cache(cassette_path, cassette_dict)
        CACHED_CASSETTES[cassette_path] = cassette_record

    @staticmethod
    def _cassette_record_for_cache(cassette_path, cassette_dict):
        """Collect all information about a cassette needed to perform the cache checks."""
        cassette_disk_mtime = os.path.getmtime(cassette_path)
        num_recordings = len(cassette_dict)

        cassette_record = {
            "cassette": cassette_dict,
            "mtime": cassette_disk_mtime,
            "num_recordings": num_recordings,
        }
        return cassette_record
