"""Fail if a public symbol of vcrpy has an unknown or ambiguous type.

Reads the output of ``pyright --verifytypes vcr --ignoreexternal --outputjson``. The stubs of
the HTTP libraries, the patching machinery and the migration script aren't annotated yet.
"""

from __future__ import annotations

import json
import sys
from typing import TypedDict

NOT_YET_ANNOTATED = ("vcr.stubs", "vcr.patch", "vcr.migration")


class _Diagnostic(TypedDict):
    message: str


class _Symbol(TypedDict):
    name: str
    isExported: bool
    isTypeKnown: bool
    isTypeAmbiguous: bool
    diagnostics: list[_Diagnostic]


class _TypeCompleteness(TypedDict):
    symbols: list[_Symbol]


class _Report(TypedDict):
    typeCompleteness: _TypeCompleteness


def _annotated(name: str) -> bool:
    return not any(name == module or name.startswith(module + ".") for module in NOT_YET_ANNOTATED)


def main(path: str) -> int:
    with open(path) as f:
        report: _Report = json.load(f)
    incomplete = [
        symbol
        for symbol in report["typeCompleteness"]["symbols"]
        if _annotated(symbol["name"]) and (not symbol["isTypeKnown"] or symbol["isTypeAmbiguous"])
    ]
    for symbol in incomplete:
        print(symbol["name"])
        for diagnostic in symbol["diagnostics"]:
            print(f"    {diagnostic['message']}")
    print(f"{len(incomplete)} public symbol(s) with an unknown or ambiguous type")
    return 1 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
