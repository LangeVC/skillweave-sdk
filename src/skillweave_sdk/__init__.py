"""Contract authority for SkillWeave.

This package is deliberately empty of logic. The repository owns the contract
bytes — the JSON schemas under ``schemas/`` and the taxonomy value set — and
``schema_version.toml`` is the root of the release graph that consumers pin
against. What is missing here is missing on purpose: the schemas are not yet
shipped as package data, and ``validator`` does not exist yet.

It is packaged now, ahead of that content, so that the dependency SkillWeave
core already declares (``skillweave-sdk==0.1.0``) resolves against a real
distribution instead of failing to resolve at all. Later versions add the
schemas and the validator; the import path and the version pin do not change
when they do.
"""

__all__ = ["__version__", "SCHEMA_VERSION"]

#: Distribution version. Kept equal to ``[schema].version`` in
#: ``schema_version.toml``; a test asserts the two agree.
__version__ = "0.1.0"

#: Canonical schema version consumers pin against.
SCHEMA_VERSION = "0.1.0"
