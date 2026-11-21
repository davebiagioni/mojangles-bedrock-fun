"""schema_check.SchemaStore on small hand-written draft-07 schemas (no network: $refs resolve locally)."""

from __future__ import annotations

import json

import pytest

from schema_check import SchemaStore


@pytest.fixture
def empty_store(tmp_path) -> SchemaStore:
    return SchemaStore(tmp_path)


@pytest.fixture
def ref_store(tmp_path) -> SchemaStore:
    """Schemas that $ref each other: relative paths, ../ and URL-encoded names, plus junk files."""
    files = {
        "item/1.0.0/Doc.json": {
            "$id": "/item/1.0.0/Doc.json",
            "type": "object",
            "required": ["components"],
            "properties": {
                "components": {"$ref": "./Item%20Components.json"},
                "description": {"$ref": "../shared/description.json"},
            },
        },
        "item/1.0.0/Item Components.json": {
            "$id": "/item/1.0.0/Item%20Components.json",
            "type": "object",
            "additionalProperties": False,
            "properties": {"minecraft:max_stack_size": {"type": "integer", "minimum": 1, "maximum": 64}},
        },
        "item/shared/description.json": {
            "$id": "/item/shared/description.json",
            "type": "object",
            "required": ["identifier"],
            "properties": {"identifier": {"$ref": "identifier.json"}},
        },
        "item/shared/identifier.json": {"$id": "/item/shared/identifier.json", "type": "string", "pattern": ":"},
        "item/1.0.0/no_id.json": {"type": "string"},
    }
    for rel, data in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "commented.json").write_text('// c\n{"$id": "/commented.json", "type": "null"}', encoding="utf-8")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    return SchemaStore(tmp_path)


# --------------------------------------------------------------------------- loading / lookup


def test_store_indexes_by_decoded_id(ref_store):
    assert set(ref_store.by_id) == {
        "/item/1.0.0/Doc.json",
        "/item/1.0.0/Item Components.json",
        "/item/shared/description.json",
        "/item/shared/identifier.json",
        "/commented.json",
    }


@pytest.mark.parametrize("name", ["item/1.0.0/Item Components.json", "/item/1.0.0/Item%20Components.json"])
def test_get_accepts_plain_and_encoded_names(ref_store, name):
    assert ref_store.get(name)["additionalProperties"] is False


def test_get_missing_raises_keyerror(ref_store):
    with pytest.raises(KeyError, match="not found"):
        ref_store.get("item/9.9.9/Doc.json")


def test_unresolved_ref_raises(empty_store):
    with pytest.raises(KeyError, match="unresolved"):
        empty_store.validate(1, {"$id": "/a.json", "$ref": "./missing.json"})


# --------------------------------------------------------------------------- keyword cases


def _check(store, schema, instance, valid, fragment):
    errors = store.validate(instance, schema)
    if valid:
        assert errors == []
    else:
        assert errors, f"{instance!r} should fail {schema}"
        assert any(fragment in e for e in errors), errors


CASES = [
    # (schema, instance, valid, error fragment)
    pytest.param({"type": "string"}, "x", True, "", id="type-string-ok"),
    pytest.param({"type": "string"}, 1, False, "expected string", id="type-string-bad"),
    pytest.param({"type": "integer"}, 3, True, "", id="type-int-ok"),
    pytest.param({"type": "integer"}, 3.0, True, "", id="type-int-whole-float"),
    pytest.param({"type": "integer"}, 3.5, False, "expected integer", id="type-int-fraction"),
    pytest.param({"type": "integer"}, True, False, "expected integer", id="type-int-rejects-bool"),
    pytest.param({"type": "number"}, False, False, "expected number", id="type-number-rejects-bool"),
    pytest.param({"type": "boolean"}, 0, False, "expected boolean", id="type-bool-rejects-int"),
    pytest.param({"type": "null"}, None, True, "", id="type-null"),
    pytest.param({"type": "array"}, (), False, "expected array", id="type-array-rejects-tuple"),
    pytest.param({"type": ["string", "null"]}, None, True, "", id="type-list-ok"),
    pytest.param({"type": ["string", "null"]}, 1, False, "expected string/null", id="type-list-bad"),
    pytest.param({"enum": ["a", "b"]}, "b", True, "", id="enum-ok"),
    pytest.param({"enum": ["a", "b"]}, "c", False, "not one of", id="enum-bad"),
    pytest.param({"const": 2}, 2, True, "", id="const-ok"),
    pytest.param({"const": 2}, 3, False, "must be 2", id="const-bad"),
    pytest.param({"pattern": "^a+$"}, "aaa", True, "", id="pattern-ok"),
    pytest.param({"pattern": "^a+$"}, "ab", False, "does not match pattern", id="pattern-bad"),
    pytest.param({"pattern": "^A$", "x-regex-flags": "icase"}, "a", True, "", id="pattern-icase"),
    pytest.param({"pattern": "^a$"}, 5, True, "", id="pattern-ignores-non-string"),
    pytest.param({"minLength": 2}, "a", False, "shorter than 2", id="min-length"),
    pytest.param({"maxLength": 2}, "abc", False, "longer than 2", id="max-length"),
    pytest.param({"minimum": 1, "maximum": 3}, 3, True, "", id="range-inclusive"),
    pytest.param({"minimum": 1}, 0, False, "< minimum 1", id="minimum"),
    pytest.param({"maximum": 1}, 2, False, "> maximum 1", id="maximum"),
    pytest.param({"exclusiveMinimum": 1}, 1, False, "<= exclusiveMinimum", id="exclusive-minimum"),
    pytest.param({"exclusiveMaximum": 1}, 1, False, ">= exclusiveMaximum", id="exclusive-maximum"),
    pytest.param({"multipleOf": 16}, 48, True, "", id="multiple-of-ok"),
    pytest.param({"multipleOf": 90}, 45, False, "not a multiple of 90", id="multiple-of-bad"),
    pytest.param({"required": ["a", "b"]}, {"a": 1}, False, "missing required 'b'", id="required"),
    pytest.param({"required": ["a"]}, [1], True, "", id="required-ignores-non-object"),
    pytest.param({"properties": {"a": {"type": "string"}}}, {"a": 1}, False, "$.a: expected string", id="properties"),
    pytest.param(
        {"properties": {"a": {}}, "additionalProperties": False},
        {"a": 1, "b": 2},
        False,
        "$.b: not allowed",
        id="addl-false",
    ),
    pytest.param(
        {"additionalProperties": {"type": "integer"}},
        {"x": 1, "y": "s"},
        False,
        "$.y: expected integer",
        id="addl-schema",
    ),
    pytest.param(
        {"patternProperties": {"^n_": {"type": "integer"}}, "additionalProperties": False},
        {"n_1": 1},
        True,
        "",
        id="pattern-properties-ok",
    ),
    pytest.param(
        {"patternProperties": {"^n_": {"type": "integer"}}, "additionalProperties": False},
        {"n_1": "x"},
        False,
        "$.n_1: expected integer",
        id="pattern-properties-bad",
    ),
    pytest.param({"propertyNames": {"pattern": "^[a-z]+$"}}, {"Bad": 1}, False, "[key 'Bad']", id="property-names"),
    pytest.param({"minProperties": 1}, {}, False, "at least 1 properties", id="min-properties"),
    pytest.param({"maxProperties": 1}, {"a": 1, "b": 2}, False, "at most 1 properties", id="max-properties"),
    pytest.param({"dependencies": {"a": ["b"]}}, {"a": 1}, False, "'a' requires 'b'", id="dependencies-list"),
    pytest.param(
        {"dependencies": {"a": {"required": ["c"]}}}, {"a": 1}, False, "missing required 'c'", id="dependencies-schema"
    ),
    pytest.param({"minItems": 2}, [1], False, "at least 2 items", id="min-items"),
    pytest.param({"maxItems": 1}, [1, 2], False, "at most 1 items", id="max-items"),
    pytest.param({"uniqueItems": True}, [1, 2, 3], True, "", id="unique-ok"),
    pytest.param({"uniqueItems": True}, [1, 2, 1], False, "items must be unique", id="unique-bad"),
    pytest.param(
        {"uniqueItems": True}, [{"a": 1, "b": 2}, {"b": 2, "a": 1}], False, "must be unique", id="unique-dict-key-order"
    ),
    pytest.param({"uniqueItems": False}, [1, 1], True, "", id="unique-false"),
    pytest.param({"items": {"type": "integer"}}, [1, "x"], False, "$[1]: expected integer", id="items-schema"),
    pytest.param(
        {"items": [{"type": "string"}, {"type": "integer"}]}, ["a", 1, None], True, "", id="prefix-items-extra-ok"
    ),
    pytest.param({"items": [{"type": "string"}, {"type": "integer"}]}, ["a"], True, "", id="prefix-items-short-ok"),
    pytest.param(
        {"items": [{"type": "string"}, {"type": "integer"}]},
        [1, 1],
        False,
        "$[0]: expected string",
        id="prefix-items-bad",
    ),
    pytest.param({"allOf": [{"minimum": 1}, {"maximum": 5}]}, 9, False, "> maximum 5", id="all-of"),
    pytest.param({"anyOf": [{"type": "string"}, {"type": "integer"}]}, 1, True, "", id="any-of-ok"),
    pytest.param({"anyOf": [{"type": "string"}, {"type": "integer"}]}, None, False, "none of anyOf", id="any-of-bad"),
    pytest.param({"oneOf": [{"type": "string"}, {"type": "integer"}]}, "s", True, "", id="one-of-ok"),
    pytest.param({"oneOf": [{"type": "number"}, {"type": "integer"}]}, 1, False, "matches 2 of oneOf", id="one-of-two"),
    pytest.param({"oneOf": [{"type": "string"}]}, 1, False, "matches none of oneOf", id="one-of-none"),
    pytest.param({"not": {"type": "string"}}, "s", False, "must not match", id="not"),
    pytest.param(
        {"if": {"type": "string"}, "then": {"minLength": 2}, "else": {"minimum": 5}},
        "a",
        False,
        "shorter",
        id="if-then",
    ),
    pytest.param(
        {"if": {"type": "string"}, "then": {"minLength": 2}, "else": {"minimum": 5}},
        1,
        False,
        "< minimum",
        id="if-else",
    ),
    pytest.param({"if": {"type": "string"}, "then": {"minLength": 2}}, 1, True, "", id="if-no-else"),
    pytest.param({"properties": {"a": True}}, {"a": 1}, True, "", id="true-subschema"),
    pytest.param({"x-whatever": 1, "description": "d", "title": "t"}, 1, True, "", id="unknown-keywords-ignored"),
]


@pytest.mark.parametrize(("schema", "instance", "valid", "fragment"), CASES)
def test_keywords(empty_store, schema, instance, valid, fragment):
    _check(empty_store, schema, instance, valid, fragment)


def test_false_subschema(empty_store):
    assert empty_store.validate({"a": 1}, {"properties": {"a": False}}) == ["$.a: not allowed here"]


def test_type_mismatch_stops_further_checks(empty_store):
    # a wrong type reports once, not also every keyword that no longer applies
    errors = empty_store.validate(5, {"type": "string", "enum": ["a"], "minLength": 3})
    assert errors == ["$: expected string, got int 5"]


def test_collects_all_errors_with_paths(empty_store):
    schema = {
        "type": "object",
        "required": ["id"],
        "properties": {
            "list": {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "integer"}}}}
        },
    }
    errors = empty_store.validate({"list": [{"n": 1}, {"n": "x"}, {"n": 2.5}]}, schema)
    assert errors == [
        "$: missing required 'id'",
        '$.list[1].n: expected integer, got str "x"',
        "$.list[2].n: expected integer, got float 2.5",
    ]


def test_long_values_are_shortened_in_messages(empty_store):
    [error] = empty_store.validate("z" * 200, {"enum": ["a"]})
    assert "..." in error
    assert len(error) < 120


# --------------------------------------------------------------------------- $ref


@pytest.mark.parametrize(
    ("instance", "fragment"),
    [
        pytest.param(
            {"components": {"minecraft:max_stack_size": 1}, "description": {"identifier": "a:b"}}, None, id="ok"
        ),
        pytest.param({"components": {"minecraft:max_stack_size": 99}}, "> maximum 64", id="encoded-relative-ref"),
        pytest.param({"components": {"minecraft:bogus": {}}}, "$.components.minecraft:bogus: not allowed", id="addl"),
        pytest.param(
            {"components": {}, "description": {}}, "$.description: missing required 'identifier'", id="dotdot-ref"
        ),
        pytest.param(
            {"components": {}, "description": {"identifier": "nocolon"}}, "does not match pattern", id="chained-ref"
        ),
        pytest.param({"description": {"identifier": "a:b"}}, "missing required 'components'", id="required"),
    ],
)
def test_ref_resolution(ref_store, instance, fragment):
    errors = ref_store.validate(instance, ref_store.get("item/1.0.0/Doc.json"))
    if fragment is None:
        assert errors == []
    else:
        assert any(fragment in e for e in errors), errors


def test_ref_siblings_also_apply(ref_store):
    # Mojang schemas put minProperties next to $ref; both must be enforced
    schema = {"$id": "/item/1.0.0/x.json", "$ref": "./Item%20Components.json", "minProperties": 1}
    assert ref_store.validate({}, schema) == ["$: needs at least 1 properties"]


# --------------------------------------------------------------------------- known gaps


@pytest.mark.xfail(
    strict=True,
    reason="BUG: multipleOf uses float modulo, so 0.3 is reported as not a multiple of 0.1 "
    "(latent: the Mojang schemas only use integer multipleOf today)",
)
def test_multiple_of_float_precision(empty_store):
    assert empty_store.validate(0.3, {"multipleOf": 0.1}) == []


@pytest.mark.xfail(
    strict=True,
    reason="BUG: enum/const compare with Python ==, so true matches enum [1] and 0 matches const false",
)
@pytest.mark.parametrize(
    ("schema", "instance"),
    [
        pytest.param({"enum": [1, 2]}, True, id="true-in-enum-1"),
        pytest.param({"const": False}, 0, id="0-equals-const-false"),
    ],
)
def test_enum_const_distinguish_bool_from_number(empty_store, schema, instance):
    assert empty_store.validate(instance, schema) != []
