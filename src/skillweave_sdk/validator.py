"""Schema validator for the SkillWeave SDK.

This module is the SDK's only validation surface. It is intentionally
dependency-free (Python standard library only): the SDK must install in a
clean environment without pulling the SkillWeave runtime.

It implements the subset of JSON Schema Draft 2020-12 that the SDK schemas
actually use, resolves cross-schema ``$ref`` by ``$id`` through a registry,
and exposes the canonical schema digest that every consumer pins.

The subset covers: ``$ref``, ``type``, ``required``, ``properties``,
``additionalProperties`` (boolean), ``items``, ``enum``, ``const``, ``oneOf``,
``allOf``, ``if``/``then``, ``minimum``, ``minItems``, ``minLength``,
``uniqueItems``, ``pattern``. Unrecognised keywords are ignored,
as Draft 2020-12 permits.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from importlib.resources import files as _resources_files
except ImportError:
    # Python < 3.9 fallback (importlib_resources backport or
    # importlib.resources without .files).
    try:
        from importlib.resources import files as _resources_files
    except ImportError:
        _resources_files = None  # type: ignore[assignment]

# All schema filenames in the SDK contract set: 4 core + 9 lifecycle.
SCHEMA_FILENAMES = (
    "evidence.schema.json",
    "prompt-sequence.schema.json",
    "run-state.schema.json",
    "workflow-context.schema.json",
    "work-profile.schema.json",
    "lifecycle-profile.schema.json",
    "deliverable-contract.schema.json",
    "evidence-contract.schema.json",
    "category-pack.schema.json",
    "category-taxonomy.schema.json",
    "model-provider.schema.json",
    "search-provider.schema.json",
    "subject-ref.schema.json",
)

# Canonical digest is computed over the sorted-key canonical JSON of every
# schema, concatenated in sorted-filename order. It changes iff the
# byte set changes.
EXPECTED_SCHEMA_DIGEST = "f2ec1b0218dd380341cffb8bce80fc8d272d07ba244287f8af1ec6feb0db18d6"


class SchemaDigestError(Exception):
    """Raised when the computed schema digest diverges from the canonical one."""


class SchemaError(Exception):
    """Raised when a schema file is missing or malformed."""


def _default_schemas_dir() -> Path:
    env = os.environ.get("SKILLWEAVE_SCHEMA_DIR")
    if env:
        return Path(env)
    if _resources_files is not None:
        try:
            return Path(str(_resources_files("skillweave_sdk") / "schemas"))
        except Exception:
            pass
    # Fallback: resolve relative to this file (source-tree dev).
    return Path(__file__).resolve().parent / "schemas"


def _canonical(schema: dict) -> bytes:
    return json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_schema(schemas_dir: Path, filename: str) -> dict:
    path = schemas_dir / filename
    if not path.is_file():
        raise SchemaError(f"missing schema file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid JSON in {path}: {exc}") from exc


def load_registry(schemas_dir: Path | None = None) -> dict[str, dict]:
    """Map every SDK schema's ``$id`` to its parsed schema object."""
    schemas_dir = schemas_dir or _default_schemas_dir()
    registry: dict[str, dict] = {}
    for filename in SCHEMA_FILENAMES:
        schema = read_schema(schemas_dir, filename)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise SchemaError(f"{filename}: missing string $id")
        registry[schema_id] = schema
    return registry


def canonical_digest(schemas_dir: Path | None = None) -> str:
    schemas_dir = schemas_dir or _default_schemas_dir()
    hasher = hashlib.sha256()
    for filename in sorted(SCHEMA_FILENAMES):
        hasher.update(filename.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(_canonical(read_schema(schemas_dir, filename)))
        hasher.update(b"\x00")
    return hasher.hexdigest()


def verify_canonical_digest(
    schemas_dir: Path | None = None,
    expected: str | None = None,
) -> None:
    """Verify the canonical schema digest.

    When *expected* is ``None`` (the normal case) the canonical digest embedded
    in this module is used. Callers that need to pin a specific SHA (e.g. a
    gate manifest) pass it explicitly.
    """
    if expected is None:
        expected = EXPECTED_SCHEMA_DIGEST
    computed = canonical_digest(schemas_dir)
    if computed != expected:
        raise SchemaDigestError(
            f"schema digest drifted: computed {computed}, "
            f"expected {expected}"
        )


# --- validation -----------------------------------------------------------

_TYPE = {
    dict: "object",
    list: "array",
    str: "string",
    bool: "boolean",
    int: "integer",
    float: "number",
    type(None): "null",
}


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return expected == _TYPE.get(type(value))


def _deep_equal(a: Any, b: Any) -> bool:
    return a == b


def _resolve_ref(
    ref: str, root_schema: dict, registry: dict[str, dict]
) -> tuple[dict, dict]:
    """Resolve a ``$ref`` and return ``(schema, new_root)``.

    Local pointers resolve against the current root; a URI ``$id`` ref switches
    the root to the referenced file's schema so that its own ``#/...`` pointers
    resolve against it. A ``$ref`` with a fragment (e.g.
    ``https://.../v1#/$defs/category``) resolves the base URI in the registry
    then follows the JSON Pointer fragment.
    """
    if ref.startswith("#"):
        resolved = _resolve_pointer(root_schema, ref[1:])
        if not isinstance(resolved, dict):
            raise SchemaError(f"$ref does not resolve to a schema: {ref}")
        return resolved, root_schema
    if "#" in ref:
        base_uri, _, fragment = ref.partition("#")
        if base_uri in registry:
            resolved = _resolve_pointer(registry[base_uri], fragment)
            if not isinstance(resolved, dict):
                raise SchemaError(f"$ref does not resolve to a schema: {ref}")
            return resolved, registry[base_uri]
    if ref in registry:
        return registry[ref], registry[ref]
    raise SchemaError(f"unresolved $ref: {ref}")


def _resolve_pointer(root: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return root
    node = root
    for part in pointer.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit():
            node = node[int(part)]
        else:
            raise SchemaError(f"unresolved JSON pointer fragment: {pointer}")
    return node


def _validate(
    instance: Any,
    schema: dict,
    registry: dict[str, dict],
    path: str,
    root_schema: dict,
) -> list[str]:
    errors: list[str] = []

    ref = schema.get("$ref")
    if isinstance(ref, str):
        resolved, new_root = _resolve_ref(ref, root_schema, registry)
        return _validate(instance, resolved, registry, path, new_root)

    if "enum" in schema:
        enum = schema["enum"]
        if not any(_deep_equal(instance, member) for member in enum):
            errors.append(f"{path}: not one of {enum!r}")

    if "const" in schema:
        if not _deep_equal(instance, schema["const"]):
            errors.append(f"{path}: must be {schema['const']!r}")

    type_spec = schema.get("type")
    if type_spec is not None:
        types = type_spec if isinstance(type_spec, list) else [type_spec]
        if not any(_matches_type(instance, t) for t in types):
            errors.append(
                f"{path}: expected type {type_spec!r}, got "
                f"{_TYPE.get(type(instance))!r}"
            )

    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance < schema["minimum"]:
            errors.append(
                f"{path}: {instance} is less than minimum {schema['minimum']}"
            )

    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            errors.append(
                f"{path}: length {len(instance)} is less than minimum "
                f"{schema['minLength']}"
            )

    if "pattern" in schema and isinstance(instance, str):
        if re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")

    if "minItems" in schema and isinstance(instance, list):
        if len(instance) < schema["minItems"]:
            errors.append(
                f"{path}: expected at least {schema['minItems']} items, "
                f"got {len(instance)}"
            )

    if "uniqueItems" in schema and isinstance(instance, list):
        if schema["uniqueItems"]:
            seen = []
            for idx, item in enumerate(instance):
                for prev in seen:
                    if _deep_equal(item, prev):
                        errors.append(f"{path}[{idx}]: duplicate item")
                        break
                seen.append(item)

    if "allOf" in schema:
        all_of = schema["allOf"]
        for idx, subschema in enumerate(all_of):
            errors.extend(
                _validate(instance, subschema, registry, f"{path} (allOf[{idx}])", root_schema)
            )

    if "if" in schema:
        if_errors = _validate(instance, schema["if"], registry, path, root_schema)
        if not if_errors:
            if "then" in schema:
                errors.extend(
                    _validate(instance, schema["then"], registry, path, root_schema)
                )
        else:
            if "else" in schema:
                errors.extend(
                    _validate(instance, schema["else"], registry, path, root_schema)
                )

    if "oneOf" in schema:
        branch_results = []
        for branch in schema["oneOf"]:
            branch_results.append(
                _validate(instance, branch, registry, path, root_schema)
            )
        passing = [1 for be in branch_results if not be]
        if sum(passing) != 1:
            errors.append(
                f"{path}: must match exactly one of "
                f"{len(schema['oneOf'])} variants"
            )

    if "required" in schema and isinstance(instance, dict):
        for key in schema["required"]:
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")

    if "properties" in schema and isinstance(instance, dict):
        props = schema["properties"]
        for key, subschema in props.items():
            if key in instance:
                errors.extend(
                    _validate(
                        instance[key], subschema, registry,
                        f"{path}.{key}", root_schema,
                    )
                )
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(
                        f"{path}: additional property {key!r} is not allowed"
                    )

    if "items" in schema and isinstance(instance, list):
        items_schema = schema["items"]
        for idx, item in enumerate(instance):
            errors.extend(
                _validate(item, items_schema, registry, f"{path}[{idx}]", root_schema)
            )

    return errors


def validate(
    instance: Any,
    schema_id: str,
    schemas_dir: Path | None = None,
) -> list[str]:
    """Validate *instance* against the schema identified by *schema_id*.

    Returns a list of error strings; an empty list means valid.
    """
    registry = load_registry(schemas_dir or _default_schemas_dir())
    if schema_id not in registry:
        raise SchemaError(f"unknown schema id: {schema_id}")
    return _validate(
        instance, registry[schema_id], registry, "$", registry[schema_id]
    )


def validate_file(path: Path, schema_id: str) -> list[str]:
    return validate(json.loads(path.read_text(encoding="utf-8")), schema_id)
