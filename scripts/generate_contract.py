#!/usr/bin/env python3
"""Erzeugt contract/run-state.enum.json AUS dem Schema und der SDK-Version.

Konstruktion statt Waechter (docs/repo-vierteilung-contract.md §C.2 im Core):
der contract/*.json-Extrakt ist ein ABGELEITETES Artefakt, kein eigenstaendig
bearbeitetes Dokument. Er kann nicht driften, weil er keinen handschriftlichen
Weg in den Baum hat — er wird immer aus run-state.schema.json erzeugt.

Die schema_version im Extrakt ist ebenfalls abgeleitet (aus
schema_version.toml), nie von Hand gesetzt. Eine eigenstaendige Zahl dort waere
eine weitere Drift-Stelle (zweite/mehrfache Wahrheit).

Aufruf:
    python3 scripts/generate_contract.py [--check]

Ohne --check schreibt der Generator den Extrakt neu (sortiert, diff-stabil).
Mit --check vergleicht er den eingecheckten Extrakt gegen den erzeugten und
verlaesst rc!=0 bei Abweichung — der Rueckfall, wenn Konstruktion aus einem
Grund nicht greift.
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
        raise SystemExit("tomllib fehlt (Python >=3.11 noetig).")
    data = tomllib.loads(VERSION_PATH.read_text(encoding="utf-8"))
    return data["schema"]["version"]


def _read_schema_enum() -> list:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = schema["properties"]["state"]["enum"]
    if not isinstance(enum, list) or not enum:
        raise SystemExit(f"{SCHEMA_PATH}: properties.state.enum leer oder fehlt")
    return enum


def generate() -> dict:
    enum = _read_schema_enum()
    return {
        "contract": "run-state",
        "schema_version": _read_version(),
        "source": "schemas/run-state.schema.json#/properties/state/enum",
        # Sortiert fuer diff-Stabilitaet; die Reihenfolge ist keine Semantik.
        "values": sorted(enum),
    }


def main() -> int:
    check = "--check" in sys.argv[1:]
    generated = generate()

    if check:
        if not EXTRACT_PATH.is_file():
            print("DRIFT: Extrakt fehlt, muss erzeugt werden.", file=sys.stderr)
            return 1
        existing = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
        if existing != generated:
            print("DRIFT: contract/run-state.enum.json stimmt nicht mit dem "
                  "Schema ueberein. Neu erzeugen (ohne --check).", file=sys.stderr)
            return 1
        print("OK: Extrakt deckungsgleich mit Schema (erzeugt, nicht handschriftlich).")
        return 0

    EXTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(generated, indent=2, ensure_ascii=False) + "\n"
    EXTRACT_PATH.write_text(text, encoding="utf-8")
    print(f"Erzeugt: {EXTRACT_PATH.relative_to(ROOT)} "
          f"(schema_version={generated['schema_version']}, "
          f"{len(generated['values'])} Werte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
