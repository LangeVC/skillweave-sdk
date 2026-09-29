"""The packaged version and the contract version are one number, checked not derived."""

import re
from pathlib import Path

import skillweave_sdk

ROOT = Path(__file__).resolve().parents[1]


def _schema_version() -> str:
    text = (ROOT / "schema_version.toml").read_text(encoding="utf-8")
    section = text.split("[schema]", 1)[1].split("[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"', section, re.MULTILINE)
    assert match, "schema_version.toml has no [schema] version"
    return match.group(1)


def _project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = text.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"', section, re.MULTILINE)
    assert match, "pyproject.toml has no [project] version"
    return match.group(1)


def test_all_three_versions_agree():
    schema, project = _schema_version(), _project_version()
    assert project == schema, (
        f"pyproject declares {project} but schema_version.toml declares {schema}; "
        "the distribution and the contract are one number"
    )
    assert skillweave_sdk.__version__ == schema
    assert skillweave_sdk.SCHEMA_VERSION == schema
