"""A small draft-07 JSON Schema validator for the Mojang schemas in bedrock-samples.

No third-party dependency (jsonschema isn't installed here). Supports the keywords those
schemas actually use: $ref (relative to $id, URL-encoded names), type, enum, const,
properties, required, additionalProperties, patternProperties, propertyNames,
min/maxProperties, items, min/maxItems, uniqueItems, pattern (+ x-regex-flags icase),
min/maxLength, minimum/maximum/exclusive*, multipleOf, oneOf/anyOf/allOf/not, if/then/else.
Unknown keywords (x-*, description, default, title...) are ignored.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin

from common import strip_json_comments


class SchemaStore:
    def __init__(self, root: Path):
        self.root = root
        self.by_id: dict[str, dict] = {}
        for p in root.rglob("*.json"):
            try:
                s = json.loads(strip_json_comments(p.read_text(encoding="utf-8-sig")))
            except (OSError, ValueError):
                continue
            sid = s.get("$id") if isinstance(s, dict) else None
            if sid:
                self.by_id[self._norm(sid)] = s

    @staticmethod
    def _norm(uri: str) -> str:
        return unquote(uri.split("#")[0])

    def get(self, rel_path: str) -> dict:
        key = self._norm("/" + rel_path.lstrip("/"))
        if key not in self.by_id:
            raise KeyError(f"schema {rel_path} not found under {self.root}")
        return self.by_id[key]

    def resolve(self, base_id: str, ref: str) -> dict:
        target = self._norm(urljoin("http://x" + base_id, ref)[len("http://x"):])
        if target not in self.by_id:
            raise KeyError(f"unresolved $ref {ref!r} from {base_id}")
        return self.by_id[target]

    def validate(self, instance, schema: dict) -> list[str]:
        errors: list[str] = []
        self._v(instance, schema, schema.get("$id", "/"), "$", errors)
        return errors

    # ------------------------------------------------------------------ core
    def _ok(self, instance, schema, base) -> bool:
        errs: list[str] = []
        self._v(instance, schema, base, "$", errs)
        return not errs

    def _v(self, inst, s, base: str, path: str, errs: list[str]) -> None:
        if s is True or s is None:
            return
        if s is False:
            errs.append(f"{path}: not allowed here")
            return
        if "$id" in s:
            base = self._norm(s["$id"])
        if "$ref" in s:
            target = self.resolve(base, s["$ref"])
            self._v(inst, target, self._norm(target.get("$id", base)), path, errs)

        t = s.get("type")
        if t is not None:
            types = t if isinstance(t, list) else [t]
            if not any(_is_type(inst, x) for x in types):
                errs.append(f"{path}: expected {'/'.join(types)}, got {type(inst).__name__} {_short(inst)}")
                return
        if "enum" in s and inst not in s["enum"]:
            errs.append(f"{path}: {_short(inst)} not one of {s['enum']}")
        if "const" in s and inst != s["const"]:
            errs.append(f"{path}: must be {s['const']!r}")

        if isinstance(inst, str):
            if "pattern" in s:
                flags = re.I if "icase" in str(s.get("x-regex-flags", "")) else 0
                if not re.search(s["pattern"], inst, flags):
                    errs.append(f"{path}: {inst!r} does not match pattern {s['pattern']!r}")
            if "minLength" in s and len(inst) < s["minLength"]:
                errs.append(f"{path}: shorter than {s['minLength']}")
            if "maxLength" in s and len(inst) > s["maxLength"]:
                errs.append(f"{path}: longer than {s['maxLength']}")
        if _is_type(inst, "number"):
            if "minimum" in s and inst < s["minimum"]:
                errs.append(f"{path}: {inst} < minimum {s['minimum']}")
            if "maximum" in s and inst > s["maximum"]:
                errs.append(f"{path}: {inst} > maximum {s['maximum']}")
            if "exclusiveMinimum" in s and inst <= s["exclusiveMinimum"]:
                errs.append(f"{path}: {inst} <= exclusiveMinimum {s['exclusiveMinimum']}")
            if "exclusiveMaximum" in s and inst >= s["exclusiveMaximum"]:
                errs.append(f"{path}: {inst} >= exclusiveMaximum {s['exclusiveMaximum']}")
            if "multipleOf" in s and (inst / s["multipleOf"]) % 1:
                errs.append(f"{path}: {inst} not a multiple of {s['multipleOf']}")

        if isinstance(inst, dict):
            props = s.get("properties", {})
            for req in s.get("required", []):
                if req not in inst:
                    errs.append(f"{path}: missing required '{req}'")
            if "minProperties" in s and len(inst) < s["minProperties"]:
                errs.append(f"{path}: needs at least {s['minProperties']} properties")
            if "maxProperties" in s and len(inst) > s["maxProperties"]:
                errs.append(f"{path}: at most {s['maxProperties']} properties")
            pprops = s.get("patternProperties", {})
            for k, v in inst.items():
                sub = f"{path}.{k}"
                if "propertyNames" in s:
                    self._v(k, s["propertyNames"], base, f"{path}[key {k!r}]", errs)
                matched = False
                if k in props:
                    matched = True
                    self._v(v, props[k], base, sub, errs)
                for pat, ps in pprops.items():
                    if re.search(pat, k):
                        matched = True
                        self._v(v, ps, base, sub, errs)
                if not matched and "additionalProperties" in s:
                    self._v(v, s["additionalProperties"], base, sub, errs)
            deps = s.get("dependencies", {})
            for k, dep in deps.items():
                if k in inst:
                    if isinstance(dep, list):
                        for d in dep:
                            if d not in inst:
                                errs.append(f"{path}: '{k}' requires '{d}'")
                    else:
                        self._v(inst, dep, base, path, errs)

        if isinstance(inst, list):
            if "minItems" in s and len(inst) < s["minItems"]:
                errs.append(f"{path}: needs at least {s['minItems']} items")
            if "maxItems" in s and len(inst) > s["maxItems"]:
                errs.append(f"{path}: at most {s['maxItems']} items")
            if s.get("uniqueItems"):
                seen = [json.dumps(x, sort_keys=True) for x in inst]
                if len(seen) != len(set(seen)):
                    errs.append(f"{path}: items must be unique")
            items = s.get("items")
            if isinstance(items, list):
                for i, (x, sch) in enumerate(zip(inst, items)):
                    self._v(x, sch, base, f"{path}[{i}]", errs)
            elif items is not None:
                for i, x in enumerate(inst):
                    self._v(x, items, base, f"{path}[{i}]", errs)

        if "allOf" in s:
            for sub in s["allOf"]:
                self._v(inst, sub, base, path, errs)
        if "anyOf" in s and not any(self._ok(inst, sub, base) for sub in s["anyOf"]):
            errs.append(f"{path}: {_short(inst)} matches none of anyOf")
        if "oneOf" in s:
            n = sum(self._ok(inst, sub, base) for sub in s["oneOf"])
            if n != 1:
                detail = "none" if n == 0 else f"{n}"
                errs.append(f"{path}: {_short(inst)} matches {detail} of oneOf (needs exactly 1)")
        if "not" in s and self._ok(inst, s["not"], base):
            errs.append(f"{path}: must not match 'not' schema")
        if "if" in s:
            branch = "then" if self._ok(inst, s["if"], base) else "else"
            if branch in s:
                self._v(inst, s[branch], base, path, errs)


def _is_type(x, t: str) -> bool:
    if t == "object":
        return isinstance(x, dict)
    if t == "array":
        return isinstance(x, list)
    if t == "string":
        return isinstance(x, str)
    if t == "boolean":
        return isinstance(x, bool)
    if t == "integer":
        return isinstance(x, int) and not isinstance(x, bool) or (isinstance(x, float) and x.is_integer())
    if t == "number":
        return isinstance(x, (int, float)) and not isinstance(x, bool)
    if t == "null":
        return x is None
    return True


def _short(x) -> str:
    s = json.dumps(x)
    return s if len(s) <= 60 else s[:57] + "..."
