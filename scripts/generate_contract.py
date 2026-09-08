#!/usr/bin/env python3
"""Generate contract/run-state.enum.json FROM the schema and the SDK version.

Construction rather than a guard: the contract/*.json extract is a DERIVED
artefact, not a document edited in its own right. It cannot drift because it has
no hand-written route into the tree — it is always generated from
run-state.schema.json.

The schema_version in the extract is likewise derived, from schema_version.toml,
never set by hand. A number standing on its own there would be one more place to
drift: a second truth.

Usage:
    python3 scripts/generate_contract.py [--check]

Without --check the generator rewrites the extract, sorted and diff-stable. With
--check it compares the committed extract against the generated one and exits
non-zero on any difference — the fallback, for when construction does not take
hold for some reason.
"""
import json
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "run-state.schema.json"
VERSION_PATH = ROOT / "schema_version.toml"
EXTRACT_PATH = ROOT / "contract" / "run-state.enum.json"


def _read_version() -> str:
    if tomllib is None:
        raise SystemExit("tomllib is missing; Python >= 3.11 is required.")
    data = tomllib.loads(VERSION_PATH.read_text(encoding="utf-8"))
    return data["schema"]["version"]


def _read_schema_enum() -> list:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = schema["properties"]["state"]["enum"]
    if not isinstance(enum, list) or not enum:
        raise SystemExit(f"{SCHEMA_PATH}: properties.state.enum is empty or absent")
    return enum


def generate() -> dict:
    enum = _read_schema_enum()
    return {
        "contract": "run-state",
        "schema_version": _read_version(),
        "source": "schemas/run-state.schema.json#/properties/state/enum",
        # Sorted for diff stability; the order carries no semantics.
        "values": sorted(enum),
    }


def main() -> int:
    check = "--check" in sys.argv[1:]
    generated = generate()

    if check:
        if not EXTRACT_PATH.is_file():
            print("DRIFT: the extract is absent and must be generated.", file=sys.stderr)
            return 1
        existing = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
        if existing != generated:
            print("DRIFT: contract/run-state.enum.json does not agree with the "
                  "schema. Regenerate it (without --check).", file=sys.stderr)
            return 1
        print("OK: extract agrees with the schema (generated, not hand-written).")
        return 0

    EXTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(generated, indent=2, ensure_ascii=False) + "\n"
    EXTRACT_PATH.write_text(text, encoding="utf-8")
    print(f"Generated: {EXTRACT_PATH.relative_to(ROOT)} "
          f"(schema_version={generated['schema_version']}, "
          f"{len(generated['values'])} values)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
