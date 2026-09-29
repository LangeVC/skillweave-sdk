"""Contract authority for SkillWeave.

The repository owns the contract bytes — the JSON schemas under ``schemas/``
and the taxonomy value set — and ``schema_version.toml`` is the root of the
release graph that consumers pin against.

``validator`` exposes the standalone, dependency-free validator that loads by
schema ID, resolves cross-schema ``$ref``, and computes the canonical digest.
"""

__all__ = ["__version__", "SCHEMA_VERSION", "validator"]

#: Distribution version. Kept equal to ``[schema].version`` in
#: ``schema_version.toml``; a test asserts the two agree.
__version__ = "0.2.0"

#: Canonical schema version consumers pin against.
SCHEMA_VERSION = "0.2.0"
