"""Deterministic table demo, Python 3.9+ standard library; no neural model.

JSON grid input only. See README.md for schema and deliberately bounded grammar.
"""
import argparse
import copy
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent
SCHEMA = {"id": "annual-wide-v1", "dimensions": ["Area", "Category"],
          "role_header": "Role", "period_pattern": "[0-9]{4}",
          "roles": ["detail", "total"], "total_dimension": "Area"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numeric(value):
    # No silent stripping of footnotes, separators, missing markers or formulas.
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("Expected a plain decimal string")
    if len(value) > 100:
        raise ValueError("Numeric cell exceeds 100-character bound")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal") from exc


def normalize(data, schema, source_file):
    if not isinstance(data, dict) or not isinstance(data.get("metadata", {}), dict):
        raise ValueError("Input and metadata must be JSON objects")
    dims = schema.get("dimensions")
    if (not isinstance(dims, list) or not dims or any(not isinstance(d, str) or not d for d in dims)
            or len(set(dims)) != len(dims) or schema.get("role_header") in dims
            or schema.get("total_dimension") not in dims or schema.get("roles") != ["detail", "total"]):
        raise ValueError("Invalid schema dimensions, role header or total rule")
    result = {"schema_id": schema["id"], "metadata": copy.deepcopy(data.get("metadata", {})),
              "dimensions": schema["dimensions"], "measures": [], "periods": [],
              "candidate_code_lists": {}, "observations": [], "issues": [],
              "extraction_confidence": {"score": None, "basis": "deterministic structural checks only"},
              "review_status": "needs_review", "totals_validation": "not_available"}
    errors = result["issues"]
    meta = result["metadata"]
    for key in ("document_id", "table_id", "title", "units", "measure", "evidence_kind", "source", "notes"):
        if key not in meta:
            errors.append("Missing metadata: " + key)
    for key in ("document_id", "table_id", "units", "measure", "evidence_kind"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            errors.append("Required nonempty string: " + key)
    if not isinstance(meta.get("title"), dict) or not any(meta.get("title", {}).values()):
        errors.append("title must contain language-keyed text")
    if not isinstance(meta.get("notes"), list):
        errors.append("notes must be a list")
    source = meta.get("source", {})
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    for field in ("page", "start_row", "start_column"):
        if field in source and (type(source[field]) is not int or source[field] < 1):
            errors.append("Source " + field + " must be a positive integer")
    if ("start_row" in source) != ("start_column" in source):
        errors.append("Source grid origin needs both start_row and start_column")
    if "sheet" in source and (not isinstance(source["sheet"], str) or not source["sheet"].strip()):
        errors.append("Source sheet must be nonempty text")
    headers, rows = data.get("headers"), data.get("rows")
    fixed = schema["dimensions"] + [schema["role_header"]]
    if not isinstance(headers, list) or any(not isinstance(h, str) for h in headers):
        errors.append("headers must be a list of strings")
        return result
    periods = headers[len(fixed):]
    if (headers[:len(fixed)] != fixed or not periods or len(set(headers)) != len(headers)
            or any(not re.fullmatch(schema["period_pattern"], p) for p in periods)):
        errors.append("Header alignment/schema mismatch: exact dimension/role columns then unique annual periods required")
        return result
    result["periods"] = periods
    result["measures"] = [{"id": meta.get("measure"), "units": meta.get("units")}]
    if not isinstance(rows, list) or not rows:
        errors.append("rows must be a nonempty list")
        return result
    if errors:
        return result
    fingerprint = hashlib.sha256(Path(source_file).read_bytes()).hexdigest()

    def provenance(row, column):
        p = {"input_file": str(Path(source_file).resolve()), "input_sha256": fingerprint,
             "json_pointer": f"/rows/{row}/{column}", "header_pointer": f"/headers/{column}",
             "document_id": meta["document_id"], "table_id": meta["table_id"],
             "source": copy.deepcopy(source)}
        if "start_row" in source:
            # start_row is the header's source row; coordinates are supplied, not independently verified.
            p["supplied_source_cell"] = {"row": source["start_row"] + row + 1,
                                         "column": source["start_column"] + column}
        return p

    seen = set()
    for r, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(headers):
            errors.append(f"/rows/{r}: width does not match headers")
            continue
        labels = row[:len(schema["dimensions"])]
        if any(not isinstance(x, str) or not x.strip() or x != x.strip() for x in labels):
            errors.append(f"/rows/{r}: missing or whitespace-padded dimension value")
            continue
        role = row[len(schema["dimensions"])]
        if role not in schema["roles"]:
            errors.append(f"/rows/{r}: unknown row role")
            continue
        for c, period in enumerate(periods, len(fixed)):
            key = tuple(labels) + (period,)
            if key in seen:
                errors.append(f"/rows/{r}/{c}: duplicate observation key")
            seen.add(key)
            try:
                value = str(numeric(row[c]))
            except ValueError as exc:
                errors.append(f"/rows/{r}/{c}: {exc}")
                continue
            result["observations"].append({"dimensions": dict(zip(schema["dimensions"], labels)),
                "period": period, "measure": meta["measure"], "unit": meta["units"],
                "value": value, "value_type": "decimal_string", "role": role,
                "provenance": provenance(r, c),
                "dimension_provenance": {d: provenance(r, i) for i, d in enumerate(schema["dimensions"])}})
    for dim in schema["dimensions"]:
        result["candidate_code_lists"][dim] = {"authority": "unverified source labels; not official codes",
            "members": sorted({o["dimensions"][dim] for o in result["observations"]})}
    totals = [o for o in result["observations"] if o["role"] == "total"]
    if totals:
        result["totals_validation"] = "passed"
        group_dims = [d for d in schema["dimensions"] if d != schema["total_dimension"]]
        groups = set()
        for total in totals:
            group = (total["period"],) + tuple(total["dimensions"][d] for d in group_dims)
            matching = [o for o in result["observations"] if o["role"] == "detail"
                        and o["period"] == total["period"]
                        and all(o["dimensions"][d] == total["dimensions"][d] for d in group_dims)]
            with localcontext() as ctx:
                ctx.prec = 256
                valid = matching and sum(Decimal(o["value"]) for o in matching) == Decimal(total["value"])
            if group in groups or not valid:
                errors.append("Total mismatch/ambiguous total at " + total["provenance"]["json_pointer"])
                result["totals_validation"] = "failed"
            groups.add(group)
    result["review_status"] = "needs_review" if errors else "validated_structure"
    return result


def answer(table, query):
    if table["review_status"] != "validated_structure":
        raise ValueError("Table needs review; queries are blocked")
    op = query.get("op")
    required = {"lookup": {"op", "select"}, "difference": {"op", "left", "right"},
                "compare": {"op", "left", "right"}}
    if op not in required or set(query) != required[op]:
        raise ValueError("Query grammar: lookup/select or difference|compare/left/right")

    def select(selector):
        if not isinstance(selector, dict) or set(selector) != set(table["dimensions"]) | {"period"}:
            raise ValueError("Selector must specify period and every dimension exactly")
        found = [o for o in table["observations"] if o["period"] == selector["period"]
                 and all(o["dimensions"][d] == selector[d] for d in table["dimensions"])]
        if len(found) != 1:
            raise ValueError("Selector must match exactly one observation")
        return found[0]

    evidence = [select(query["select"])] if op == "lookup" else [select(query["left"]), select(query["right"])]
    with localcontext() as ctx:
        ctx.prec = 256
        value = evidence[0]["value"]
        if op != "lookup":
            a, b = (Decimal(o["value"]) for o in evidence)
            value = str(a - b) if op == "difference" else ("equal" if a == b else "greater" if a > b else "less")
    return {"operation": op, "result": value, "units": evidence[0]["unit"],
            "definition": "left minus right" if op == "difference" else op,
            "table_metadata": table["metadata"], "evidence": evidence,
            "review_status": table["review_status"]}


def fixtures():
    def table(doc, ident, years, rows):
        return {"metadata": {"document_id": doc, "table_id": ident,
            "title": {"en": "Synthetic activity counts", "ar": "أعداد أنشطة افتراضية"},
            "description": {"en": "synthetic demonstration only; not official NCSI statistics"},
            "evidence_kind": "synthetic demonstration only", "units": "demonstration units",
            "measure": "activity", "notes": ["All values and dimension members are synthetic."],
            "source": {"uri": "synthetic:" + doc, "sheet": "Demo", "start_row": 1, "start_column": 1}},
            "headers": ["Area", "Category", "Role"] + years, "rows": rows}
    baseline = table("synthetic-example", "example-A", ["2020", "2021"],
                     [["North", "A", "detail", "20", "30"],
                      ["South", "A", "detail", "30", "50"],
                      ["All", "A", "total", "50", "80"]])
    heldout = table("synthetic-heldout", "unseen-B", ["2030", "2031"],
                    [["East", "B", "detail", "10.25", "11.25"],
                     ["West", "B", "detail", "20.75", "25.75"]])
    select = {"Area": "East", "Category": "B", "period": "2031"}
    mutated = copy.deepcopy(heldout)
    mutated["rows"][0][4] = "14.25"
    return {"example.json": baseline, "heldout.json": heldout, "heldout_changed.json": mutated, "schema.json": SCHEMA,
            "lookup.json": {"op": "lookup", "select": select},
            "difference.json": {"op": "difference", "left": select,
                                "right": dict(select, period="2030")}}


class Tests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()

    def parse(self, name="heldout.json", data=None):
        # The test source is an actual temporary file; its hash matches its data.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / name
            save(path, self.f[name] if data is None else data)
            return normalize(read(path), SCHEMA, path)

    def test_exact_heldout(self):
        table = self.parse()
        self.assertEqual(answer(table, self.f["lookup.json"])["result"], "11.25")
        self.assertEqual(table["observations"][1]["provenance"]["json_pointer"], "/rows/0/4")

    def test_period_arithmetic_and_mutation(self):
        table = self.parse()
        self.assertEqual(answer(table, self.f["difference.json"])["result"], "1.00")
        changed = copy.deepcopy(self.f["heldout.json"])
        changed["rows"][0][4] = "14.25"
        after = self.parse(data=changed)
        self.assertEqual(after["observations"][1]["value"], "14.25")
        self.assertEqual(answer(after, self.f["lookup.json"])["result"], "14.25")
        self.assertEqual(answer(after, self.f["difference.json"])["result"], "4.00")
        self.assertNotEqual(table["observations"][1]["provenance"]["input_sha256"],
                            after["observations"][1]["provenance"]["input_sha256"])

    def test_totals(self):
        self.assertEqual(self.parse("example.json")["totals_validation"], "passed")
        bad = copy.deepcopy(self.f["example.json"])
        bad["rows"][0][3] = "21"
        self.assertEqual(self.parse("example.json", bad)["totals_validation"], "failed")

    def test_review_gates(self):
        for mutation in (lambda d: d["headers"].reverse(),
                         lambda d: d["rows"][0].pop(),
                         lambda d: d["rows"].append(d["rows"][0][:]),
                         lambda d: d["rows"][0].__setitem__(0, ""),
                         lambda d: d["rows"][0].__setitem__(3, "NaN"),
                         lambda d: d["metadata"]["source"].__setitem__("page", 0),
                         lambda d: d["metadata"].pop("units")):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(self.f["heldout.json"])
                mutation(bad)
                table = self.parse(data=bad)
                self.assertEqual(table["review_status"], "needs_review")
                with self.assertRaises(ValueError):
                    answer(table, self.f["lookup.json"])

    def test_comparison_and_query_rejection(self):
        table = self.parse()
        self.assertEqual(answer(table, dict(self.f["difference.json"], op="compare"))["result"], "greater")
        with self.assertRaises(ValueError):
            answer(table, {"op": "lookup", "select": {"period": "2031"}})
        with self.assertRaises(ValueError):
            answer(table, {"op": "lookup", "select": {"period": "2031", "Area": "Absent", "Category": "B"}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--make-demo", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--schema", type=Path, default=ROOT / "schema.json")
    parser.add_argument("--query", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.make_demo:
        for name, content in fixtures().items():
            path = ROOT / name
            if path.exists():
                raise ValueError("Refusing to overwrite existing fixture: " + str(path))
            save(path, content)
        print("Created synthetic demonstration only fixtures; no official NCSI data.")
    if args.test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        if not result.wasSuccessful():
            raise SystemExit(1)
    if args.input:
        if args.input.suffix.lower() != ".json":
            raise ValueError("Only documented JSON grid input is supported")
        table = normalize(read(args.input), read(args.schema), args.input)
        result = answer(table, read(args.query)) if args.query else table
        if args.output:
            save(args.output, result)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if table["review_status"] == "needs_review":
            raise SystemExit(2)
    elif not (args.make_demo or args.test):
        parser.error("Use --input, --test or --make-demo")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("Needs review: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
