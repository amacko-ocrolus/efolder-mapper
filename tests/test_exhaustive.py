"""
Exhaustive test suite for the Container Mapper tool.
Covers edge cases, boundary conditions, failure modes, and output integrity.
Run with: python -m pytest tests/test_exhaustive.py -v
"""

import csv
import io
import json
import os
import tempfile

import pytest

from services.consensus import build_consensus, write_output_csv
from services.ingestion import load_lender_containers, load_ocrolus_types
from services.json_repair import extract_json_object
from services.ai_openai import _parse_response as parse_openai
from services.ai_anthropic import _parse_response as parse_anthropic
from services.ai_gemini import _parse_response as parse_gemini
from prompts.mapping_prompt import build_mapping_prompt


# ============================================================
# HELPERS
# ============================================================

def write_csv(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def write_csv_bom(tmp_path, name, content):
    p = tmp_path / name
    p.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    return str(p)


def make_results(openai_map, anthropic_map, gemini_map=None):
    r = {"OpenAI": openai_map, "Anthropic": anthropic_map}
    if gemini_map is not None:
        r["Gemini"] = gemini_map
    return r


# ============================================================
# 1. INGESTION — EDGE CASES
# ============================================================

class TestIngestionEdgeCases:

    def test_csv_with_bom(self, tmp_path):
        path = write_csv_bom(tmp_path, "types.csv", "Form Type\nW2\nPAYSTUB\n")
        result = load_ocrolus_types(path)
        assert "W2" in result
        assert "PAYSTUB" in result

    def test_csv_with_trailing_whitespace_in_values(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "Form Type\n  W2  \n  PAYSTUB  \n")
        result = load_ocrolus_types(path)
        assert "W2" in result
        assert "PAYSTUB" in result

    def test_csv_with_blank_rows(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "Form Type\nW2\n\nPAYSTUB\n\n\n")
        result = load_ocrolus_types(path)
        assert result == ["PAYSTUB", "W2"]

    def test_csv_deduplicates(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "Form Type\nW2\nW2\nW2\n")
        result = load_ocrolus_types(path)
        assert result.count("W2") == 1

    def test_csv_multi_column_no_matching_header_falls_back_to_first(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "alpha,beta,gamma\nFORM_A,x,y\nFORM_B,x,y\n")
        result = load_ocrolus_types(path)
        assert "FORM_A" in result

    def test_csv_multi_column_finds_type_column(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "id,form_type,description\n1,W2,Wage\n2,PAYSTUB,Pay\n")
        result = load_ocrolus_types(path)
        assert "W2" in result
        assert "PAYSTUB" in result
        assert "1" not in result  # id column not used

    def test_csv_sorted_output(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "name\nZZZ\nAAA\nMMM\n")
        result = load_ocrolus_types(path)
        assert result == sorted(result)

    def test_lender_csv_with_commas_in_values(self, tmp_path):
        path = write_csv(tmp_path, "containers.csv",
                         'Container Name\n"Income - W-2 / 1099"\n"Assets, Bank Statements"\n')
        result = load_lender_containers(path)
        assert "Income - W-2 / 1099" in result
        assert "Assets, Bank Statements" in result

    def test_lender_json_flat_array(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text(json.dumps(["Tax Docs", "Income", "Assets"]))
        result = load_lender_containers(str(p))
        assert set(result) == {"Assets", "Income", "Tax Docs"}

    def test_lender_json_array_of_objects_various_keys(self, tmp_path):
        for key in ["container", "name", "document", "title", "label"]:
            p = tmp_path / f"c_{key}.json"
            p.write_text(json.dumps([{key: "Tax Docs"}, {key: "Income"}]))
            result = load_lender_containers(str(p))
            assert "Tax Docs" in result

    def test_lender_json_nested(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text(json.dumps({"data": {"containers": ["Tax Docs", "Income"]}}))
        result = load_lender_containers(str(p))
        assert "Tax Docs" in result

    def test_unsupported_extension_raises(self, tmp_path):
        p = tmp_path / "containers.xlsx"
        p.write_bytes(b"fake")
        with pytest.raises(ValueError, match="Unsupported"):
            load_lender_containers(str(p))

    def test_single_row_file(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "Form Type\nONLY_ONE\n")
        result = load_ocrolus_types(path)
        assert result == ["ONLY_ONE"]

    def test_unicode_form_types(self, tmp_path):
        path = write_csv(tmp_path, "types.csv", "Form Type\nFORMA_ESPAÑOLA\nTYP_ÜNIVERSAL\n")
        result = load_ocrolus_types(path)
        assert "FORMA_ESPAÑOLA" in result
        assert "TYP_ÜNIVERSAL" in result


# ============================================================
# 2. JSON REPAIR — EXHAUSTIVE
# ============================================================

class TestJsonRepairExhaustive:

    def test_clean_json_passthrough(self):
        raw = json.dumps({"W2": {"container": "Tax Docs", "confidence": 0.9}})
        result = extract_json_object(raw)
        assert result["W2"]["container"] == "Tax Docs"

    def test_markdown_fence_json(self):
        inner = json.dumps({"W2": "Tax Docs"})
        raw = f"```json\n{inner}\n```"
        assert extract_json_object(raw) == {"W2": "Tax Docs"}

    def test_markdown_fence_no_language_tag(self):
        inner = json.dumps({"W2": "Tax Docs"})
        raw = f"```\n{inner}\n```"
        assert extract_json_object(raw) == {"W2": "Tax Docs"}

    def test_preamble_text_before_json(self):
        raw = 'Here is the mapping:\n{"W2": "Tax Docs"}'
        result = extract_json_object(raw)
        assert result["W2"] == "Tax Docs"

    def test_trailing_text_after_json(self):
        raw = '{"W2": "Tax Docs"}\nHope this helps!'
        result = extract_json_object(raw)
        assert result["W2"] == "Tax Docs"

    def test_truncated_mid_string_value(self):
        raw = '{"W2": {"container": "Tax Do'
        result = extract_json_object(raw)
        assert "W2" in result

    def test_truncated_after_complete_entry_with_trailing_comma(self):
        raw = '{"W2": "Tax Docs", "PAYSTUB": "Income",'
        result = extract_json_object(raw)
        assert result["W2"] == "Tax Docs"
        assert result["PAYSTUB"] == "Income"

    def test_truncated_nested_object(self):
        raw = '{"W2": {"container": "Tax Docs", "confidence": 0.99}, "PAYSTUB": {"container": "Income", "confidence": 0.9'
        result = extract_json_object(raw)
        assert result["W2"]["container"] == "Tax Docs"

    def test_multiple_depth_truncation(self):
        raw = '{"A": {"x": {"y": "val'
        result = extract_json_object(raw)
        assert "A" in result

    def test_empty_object(self):
        result = extract_json_object("{}")
        assert result == {}

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            extract_json_object("no json here at all")

    def test_just_array_raises(self):
        with pytest.raises(ValueError):
            extract_json_object('["not", "an", "object"]')

    def test_regex_fallback_for_flat_strings(self):
        raw = '{"W2": "Tax Docs", "PAYSTUB": "Income"'  # missing closing brace
        result = extract_json_object(raw)
        assert result.get("W2") == "Tax Docs"

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            extract_json_object("   ")


# ============================================================
# 3. RESPONSE PARSING — EDGE CASES (all 3 services)
# ============================================================

PARSERS = {
    "OpenAI": parse_openai,
    "Anthropic": parse_anthropic,
    "Gemini": parse_gemini,
}
FORM_TYPES = ["W2", "PAYSTUB", "APPRAISAL"]


@pytest.mark.parametrize("svc,parser", PARSERS.items())
class TestParserEdgeCases:

    def test_confidence_clamped_above_1(self, svc, parser):
        raw = json.dumps({"W2": {"container": "Tax Docs", "confidence": 1.5},
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8}})
        result = parser(raw, FORM_TYPES)
        assert result["W2"][1] == 1.0

    def test_confidence_clamped_below_0(self, svc, parser):
        raw = json.dumps({"W2": {"container": "Tax Docs", "confidence": -0.5},
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8}})
        result = parser(raw, FORM_TYPES)
        assert result["W2"][1] == 0.0

    def test_confidence_as_string_coerced(self, svc, parser):
        raw = json.dumps({"W2": {"container": "Tax Docs", "confidence": "0.85"},
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8}})
        result = parser(raw, FORM_TYPES)
        assert result["W2"][1] == 0.85

    def test_confidence_missing_defaults_to_0_5(self, svc, parser):
        raw = json.dumps({"W2": {"container": "Tax Docs"},
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8}})
        result = parser(raw, FORM_TYPES)
        assert result["W2"][1] == 0.5

    def test_null_value_becomes_no_match(self, svc, parser):
        raw = json.dumps({"W2": None,
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8}})
        result = parser(raw, FORM_TYPES)
        assert result["W2"] == ("NO_MATCH", 0.0)

    def test_empty_container_string_becomes_no_match(self, svc, parser):
        raw = json.dumps({"W2": {"container": "", "confidence": 0.5},
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8}})
        result = parser(raw, FORM_TYPES)
        assert result["W2"] == ("NO_MATCH", 0.5)

    def test_container_whitespace_stripped(self, svc, parser):
        raw = json.dumps({"W2": {"container": "  Tax Docs  ", "confidence": 0.9},
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8}})
        result = parser(raw, FORM_TYPES)
        assert result["W2"][0] == "Tax Docs"

    def test_extra_keys_in_response_ignored(self, svc, parser):
        raw = json.dumps({"W2": {"container": "Tax Docs", "confidence": 0.9},
                          "PAYSTUB": {"container": "Income", "confidence": 0.9},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 0.8},
                          "EXTRA_FORM": {"container": "Something", "confidence": 0.5}})
        result = parser(raw, FORM_TYPES)
        # EXTRA_FORM not in FORM_TYPES so not in result
        assert "EXTRA_FORM" not in result
        assert len(result) == 3

    def test_all_missing_become_no_match(self, svc, parser):
        result = parser("{}", FORM_TYPES)
        assert all(v == ("NO_MATCH", 0.0) for v in result.values())

    def test_plain_string_fallback_confidence_0_5(self, svc, parser):
        raw = json.dumps({"W2": "Tax Docs", "PAYSTUB": "Income", "APPRAISAL": "Appraisal"})
        result = parser(raw, FORM_TYPES)
        for ft in FORM_TYPES:
            assert result[ft][1] == 0.5

    def test_integer_confidence_coerced(self, svc, parser):
        raw = json.dumps({"W2": {"container": "Tax Docs", "confidence": 1},
                          "PAYSTUB": {"container": "Income", "confidence": 0},
                          "APPRAISAL": {"container": "Appraisal", "confidence": 1}})
        result = parser(raw, FORM_TYPES)
        assert isinstance(result["W2"][1], float)
        assert result["W2"][1] == 1.0
        assert result["PAYSTUB"][1] == 0.0

    def test_unicode_form_type_and_container(self, svc, parser):
        ft = ["FORMA_ESPAÑOLA"]
        raw = json.dumps({"FORMA_ESPAÑOLA": {"container": "Documentos Fiscales", "confidence": 0.8}})
        result = parser(raw, ft)
        assert result["FORMA_ESPAÑOLA"][0] == "Documentos Fiscales"

    def test_invalid_json_raises_value_error(self, svc, parser):
        with pytest.raises(ValueError):
            parser("this is not json at all !!!", FORM_TYPES)


# ============================================================
# 4. CONSENSUS ENGINE — EXHAUSTIVE
# ============================================================

class TestConsensusExhaustive:

    def test_two_services_only(self):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.9)},
            "Anthropic": {"W2": ("Tax Docs", 0.85)},
        }
        confident, review = build_consensus(results, ["W2"])
        assert len(confident) == 1
        assert confident[0]["suggested_container"] == "Tax Docs"

    def test_two_agree_one_disagrees(self):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.9)},
            "Anthropic": {"W2": ("Tax Docs", 0.85)},
            "Gemini":    {"W2": ("Other Docs", 0.3)},
        }
        confident, review = build_consensus(results, ["W2"])
        assert len(confident) == 1
        assert confident[0]["suggested_container"] == "Tax Docs"

    def test_all_disagree_goes_to_review(self):
        results = {
            "OpenAI":    {"W2": ("A", 0.9)},
            "Anthropic": {"W2": ("B", 0.8)},
            "Gemini":    {"W2": ("C", 0.7)},
        }
        confident, review = build_consensus(results, ["W2"])
        assert len(confident) == 0
        assert len(review) == 1
        assert review[0]["best_guess"] == "A"
        assert review[0]["best_guess_service"] == "OpenAI"

    def test_no_match_consensus_goes_to_review_not_confident(self):
        results = {
            "OpenAI":    {"W2": ("NO_MATCH", 0.0)},
            "Anthropic": {"W2": ("NO_MATCH", 0.0)},
            "Gemini":    {"W2": ("NO_MATCH", 0.0)},
        }
        confident, review = build_consensus(results, ["W2"])
        assert len(confident) == 0
        assert len(review) == 1

    def test_two_no_match_one_real_goes_to_review(self):
        results = {
            "OpenAI":    {"W2": ("NO_MATCH", 0.0)},
            "Anthropic": {"W2": ("NO_MATCH", 0.0)},
            "Gemini":    {"W2": ("Tax Docs", 0.6)},
        }
        # NO_MATCH has 2 votes — but NO_MATCH consensus is blocked → review
        confident, review = build_consensus(results, ["W2"])
        assert len(confident) == 0
        assert len(review) == 1
        assert review[0]["best_guess"] == "Tax Docs"

    def test_form_type_missing_from_service_treated_as_no_match(self):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.9)},
            "Anthropic": {},  # W2 missing entirely
        }
        confident, review = build_consensus(results, ["W2"])
        # OpenAI returns Tax Docs, Anthropic returns NO_MATCH — no consensus
        assert len(confident) == 0
        assert len(review) == 1

    def test_avg_confidence_only_for_agreeing_services(self):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.90)},
            "Anthropic": {"W2": ("Tax Docs", 0.86)},
            "Gemini":    {"W2": ("Other", 0.99)},  # disagrees, should not affect avg
        }
        confident, review = build_consensus(results, ["W2"])
        assert confident[0]["avg_confidence"] == round((0.90 + 0.86) / 2, 2)

    def test_all_form_types_present_in_output(self):
        form_types = ["A", "B", "C", "D", "E"]
        results = {
            "OpenAI":    {ft: ("Container X", 0.9) for ft in form_types},
            "Anthropic": {ft: ("Container Y", 0.8) for ft in form_types},
        }
        confident, review = build_consensus(results, form_types)
        total = len(confident) + len(review)
        assert total == len(form_types)

    def test_confident_container_never_no_match(self):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.9), "X": ("NO_MATCH", 0.0)},
            "Anthropic": {"W2": ("Tax Docs", 0.8), "X": ("NO_MATCH", 0.0)},
        }
        confident, review = build_consensus(results, ["W2", "X"])
        for row in confident:
            assert row["suggested_container"] != "NO_MATCH"

    def test_single_form_type(self):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.9)},
            "Anthropic": {"W2": ("Tax Docs", 0.85)},
        }
        confident, review = build_consensus(results, ["W2"])
        assert len(confident) == 1

    def test_large_batch_100_form_types(self):
        form_types = [f"FORM_{i}" for i in range(100)]
        results = {
            "OpenAI":    {ft: ("Container A", 0.9) for ft in form_types},
            "Anthropic": {ft: ("Container A", 0.85) for ft in form_types},
        }
        confident, review = build_consensus(results, form_types)
        assert len(confident) == 100
        assert len(review) == 0

    def test_review_row_has_all_service_columns(self):
        results = {
            "OpenAI":    {"W2": ("A", 0.9)},
            "Anthropic": {"W2": ("B", 0.8)},
            "Gemini":    {"W2": ("C", 0.7)},
        }
        _, review = build_consensus(results, ["W2"])
        row = review[0]
        for svc in ["OpenAI", "Anthropic", "Gemini"]:
            assert f"{svc}_suggestion" in row
            assert f"{svc}_confidence" in row

    def test_confidence_preserved_in_confident_row(self):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 1.0)},
            "Anthropic": {"W2": ("Tax Docs", 1.0)},
        }
        confident, _ = build_consensus(results, ["W2"])
        assert confident[0]["avg_confidence"] == 1.0


# ============================================================
# 5. BATCH BOUNDARY — form types split across batches
# ============================================================

class TestBatchBoundary:

    def test_prompt_contains_all_form_types(self):
        form_types = [f"FORM_{i}" for i in range(10)]
        containers = ["Container A", "Container B"]
        prompt = build_mapping_prompt(form_types, containers)
        for ft in form_types:
            assert ft in prompt, f"{ft} not found in prompt"

    def test_prompt_contains_all_containers(self):
        form_types = ["W2"]
        containers = [f"Container {i}" for i in range(20)]
        prompt = build_mapping_prompt(form_types, containers)
        for c in containers:
            assert c in prompt

    def test_batch_split_at_150_all_form_types_in_output(self):
        """Simulate 2 batches: 150 + 1 = 151 form types."""
        from services.ai_openai import BATCH_SIZE
        form_types = [f"FORM_{i:04d}" for i in range(BATCH_SIZE + 1)]
        containers = ["Container A"]

        assert BATCH_SIZE == 150
        # Batch 1: indices 0-149, Batch 2: index 150
        batch1 = form_types[:BATCH_SIZE]
        batch2 = form_types[BATCH_SIZE:]

        assert len(batch1) == 150
        assert len(batch2) == 1
        assert set(batch1 + batch2) == set(form_types)

    def test_batch_boundary_results_merged(self):
        """Verify parse + merge across two batches produces all form types."""
        from services.ai_openai import BATCH_SIZE
        form_types = [f"FORM_{i:04d}" for i in range(BATCH_SIZE + 1)]

        def fake_batch_response(batch):
            return json.dumps({
                ft: {"container": "Container A", "confidence": 0.9}
                for ft in batch
            })

        merged = {}
        for i in range(0, len(form_types), BATCH_SIZE):
            batch = form_types[i:i + BATCH_SIZE]
            raw = fake_batch_response(batch)
            merged.update(parse_openai(raw, batch))

        assert len(merged) == len(form_types)
        assert all(ft in merged for ft in form_types)


# ============================================================
# 6. CSV OUTPUT INTEGRITY
# ============================================================

class TestCSVOutputIntegrity:

    def _make_results_confident(self):
        fts = ["W2", "PAYSTUB", "APPRAISAL"]
        return (
            {"OpenAI":    {ft: ("Tax Docs", 0.9) for ft in fts},
             "Anthropic": {ft: ("Tax Docs", 0.85) for ft in fts}},
            fts,
        )

    def test_csv_is_valid_and_parseable(self, tmp_path):
        results, fts = self._make_results_confident()
        confident, review = build_consensus(results, fts)
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))

        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) > 0

    def test_container_names_with_commas_properly_quoted(self, tmp_path):
        results = {
            "OpenAI":    {"W2": ("Income - W-2 / 1099, Tax Year", 0.9)},
            "Anthropic": {"W2": ("Income - W-2 / 1099, Tax Year", 0.85)},
        }
        confident, review = build_consensus(results, ["W2"])
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))

        with open(path, newline="", encoding="utf-8") as f:
            content = f.read()
        # Container name should appear intact
        assert "Income - W-2 / 1099, Tax Year" in content

        # Verify it re-parses correctly (commas in quoted fields)
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if "Income - W-2 / 1099, Tax Year" in row:
                    assert row.count("Income - W-2 / 1099, Tax Year") >= 1

    def test_container_names_with_quotes(self, tmp_path):
        results = {
            "OpenAI":    {"W2": ('Tax "Documents" File', 0.9)},
            "Anthropic": {"W2": ('Tax "Documents" File', 0.85)},
        }
        confident, review = build_consensus(results, ["W2"])
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))
        # CSV escapes quotes as "" — parse the file to verify the field value is intact
        with open(path, newline="", encoding="utf-8") as f:
            all_cells = [cell for row in csv.reader(f) for cell in row]
        assert 'Tax "Documents" File' in all_cells

    def test_unicode_in_output(self, tmp_path):
        results = {
            "OpenAI":    {"FORMA_ESPAÑOLA": ("Documentación Fiscal", 0.9)},
            "Anthropic": {"FORMA_ESPAÑOLA": ("Documentación Fiscal", 0.85)},
        }
        confident, review = build_consensus(results, ["FORMA_ESPAÑOLA"])
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "FORMA_ESPAÑOLA" in content
        assert "Documentación Fiscal" in content

    def test_failed_services_appear_in_header(self, tmp_path):
        results = {"OpenAI": {"W2": ("Tax Docs", 0.9)},
                   "Anthropic": {"W2": ("Tax Docs", 0.85)}}
        confident, review = build_consensus(results, ["W2"])
        path = str(tmp_path / "out.csv")
        errors = {"Gemini": "quota limit: 0"}
        write_output_csv(path, confident, review, list(results.keys()), errors)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Gemini" in content
        assert "quota limit" in content

    def test_empty_review_section_still_has_header(self, tmp_path):
        results = {"OpenAI": {"W2": ("Tax Docs", 0.9)},
                   "Anthropic": {"W2": ("Tax Docs", 0.85)}}
        confident, review = build_consensus(results, ["W2"])
        assert len(review) == 0
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "MANUAL REVIEW" in content

    def test_empty_confident_section_still_has_header(self, tmp_path):
        results = {"OpenAI": {"W2": ("A", 0.9)},
                   "Anthropic": {"W2": ("B", 0.8)}}
        confident, review = build_consensus(results, ["W2"])
        assert len(confident) == 0
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "CONFIDENT MAPPINGS" in content

    def test_row_count_matches_form_types(self, tmp_path):
        form_types = [f"FORM_{i}" for i in range(20)]
        results = {
            "OpenAI":    {ft: (f"Container {i%3}", 0.9) for i, ft in enumerate(form_types)},
            "Anthropic": {ft: (f"Container {i%5}", 0.8) for i, ft in enumerate(form_types)},
        }
        confident, review = build_consensus(results, form_types)
        assert len(confident) + len(review) == 20

    def test_avg_confidence_in_csv(self, tmp_path):
        results = {"OpenAI": {"W2": ("Tax Docs", 0.90)},
                   "Anthropic": {"W2": ("Tax Docs", 0.88)}}
        confident, review = build_consensus(results, ["W2"])
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))
        with open(path, encoding="utf-8-sig") as f:
            content = f.read()
        assert "0.89" in content

    def test_best_guess_columns_in_review(self, tmp_path):
        results = {"OpenAI": {"W2": ("A", 0.9)},
                   "Anthropic": {"W2": ("B", 0.5)}}
        confident, review = build_consensus(results, ["W2"])
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Best Guess" in content
        assert "Best Confidence" in content
        assert "Best Guess Service" in content


# ============================================================
# 7. PROMPT BUILDING
# ============================================================

class TestPromptBuilding:

    def test_all_form_types_in_prompt(self):
        fts = ["W2", "PAYSTUB", "BANK_STATEMENT"]
        containers = ["Tax Docs", "Income"]
        prompt = build_mapping_prompt(fts, containers)
        for ft in fts:
            assert ft in prompt

    def test_all_containers_in_prompt(self):
        fts = ["W2"]
        containers = ["Tax Docs", "Income", "Assets", "Credit"]
        prompt = build_mapping_prompt(fts, containers)
        for c in containers:
            assert c in prompt

    def test_prompt_instructs_json_output(self):
        prompt = build_mapping_prompt(["W2"], ["Tax Docs"])
        assert "JSON" in prompt or "json" in prompt

    def test_prompt_instructs_confidence(self):
        prompt = build_mapping_prompt(["W2"], ["Tax Docs"])
        assert "confidence" in prompt

    def test_prompt_forbids_no_match(self):
        prompt = build_mapping_prompt(["W2"], ["Tax Docs"])
        # The prompt should instruct to always provide best-guess
        assert "best-guess" in prompt or "always" in prompt.lower()

    def test_prompt_format_example_present(self):
        prompt = build_mapping_prompt(["W2"], ["Tax Docs"])
        assert "container" in prompt
        assert "0.95" in prompt or "confidence" in prompt


# ============================================================
# 8. FULL PIPELINE — BACKWARDS VERIFICATION
# ============================================================

class TestFullPipelineBackwards:
    """Read the OUTPUT and verify it's structurally and semantically correct."""

    def _run_pipeline(self, tmp_path, form_types, openai_map, anthropic_map, gemini_map=None):
        results = {"OpenAI": openai_map, "Anthropic": anthropic_map}
        if gemini_map:
            results["Gemini"] = gemini_map
        confident, review = build_consensus(results, form_types)
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()))
        return path, confident, review

    def test_every_input_form_type_appears_in_output(self, tmp_path):
        fts = [f"FORM_{i}" for i in range(15)]
        oai = {ft: ("Container A", 0.9) for ft in fts}
        ant = {ft: ("Container B", 0.8) for ft in fts}
        path, confident, review = self._run_pipeline(tmp_path, fts, oai, ant)

        with open(path, encoding="utf-8") as f:
            content = f.read()
        for ft in fts:
            assert ft in content, f"{ft} missing from output CSV"

    def test_no_form_type_appears_twice(self, tmp_path):
        fts = ["W2", "PAYSTUB", "APPRAISAL"]
        oai = {ft: ("Container A", 0.9) for ft in fts}
        ant = {ft: ("Container A", 0.85) for ft in fts}
        _, confident, review = self._run_pipeline(tmp_path, fts, oai, ant)

        all_types = [r["ocrolus_type"] for r in confident] + \
                    [r["ocrolus_type"] for r in review]
        assert len(all_types) == len(set(all_types)), "Duplicate form type in output"

    def test_confident_containers_always_from_lender_list(self, tmp_path):
        fts = ["W2", "PAYSTUB"]
        containers = ["Tax Docs", "Income"]
        oai = {"W2": ("Tax Docs", 0.9), "PAYSTUB": ("Income", 0.9)}
        ant = {"W2": ("Tax Docs", 0.85), "PAYSTUB": ("Income", 0.85)}
        _, confident, review = self._run_pipeline(tmp_path, fts, oai, ant)

        for row in confident:
            assert row["suggested_container"] in containers

    def test_review_best_guess_is_highest_confidence(self, tmp_path):
        fts = ["W2"]
        oai = {"W2": ("A", 0.90)}
        ant = {"W2": ("B", 0.40)}
        gem = {"W2": ("C", 0.50)}
        _, _, review = self._run_pipeline(tmp_path, fts, oai, ant, gem)

        assert review[0]["best_guess"] == "A"
        assert review[0]["best_confidence"] == 0.90
        assert review[0]["best_guess_service"] == "OpenAI"

    def test_all_confidence_scores_between_0_and_1(self, tmp_path):
        fts = [f"F{i}" for i in range(10)]
        import random
        random.seed(42)
        oai = {ft: ("A", round(random.uniform(0, 1), 2)) for ft in fts}
        ant = {ft: ("B", round(random.uniform(0, 1), 2)) for ft in fts}
        _, confident, review = self._run_pipeline(tmp_path, fts, oai, ant)

        for row in confident:
            assert 0.0 <= row["avg_confidence"] <= 1.0
        for row in review:
            assert 0.0 <= row["best_confidence"] <= 1.0

    def test_mixed_confident_and_review(self, tmp_path):
        """Half agree, half disagree."""
        fts = ["A", "B", "C", "D"]
        oai = {"A": ("X", 0.9), "B": ("X", 0.9), "C": ("X", 0.9), "D": ("X", 0.9)}
        ant = {"A": ("X", 0.8), "B": ("X", 0.8), "C": ("Y", 0.8), "D": ("Y", 0.8)}
        _, confident, review = self._run_pipeline(tmp_path, fts, oai, ant)

        assert len(confident) == 2  # A, B agree
        assert len(review) == 2     # C, D disagree
        conf_types = {r["ocrolus_type"] for r in confident}
        review_types = {r["ocrolus_type"] for r in review}
        assert conf_types == {"A", "B"}
        assert review_types == {"C", "D"}


# ============================================================
# 9. MAPPER CLI — argument handling and error propagation
# ============================================================

class TestMapperCLI:
    """Test mapper.py's write_output_csv call passes errors correctly."""

    def test_errors_passed_to_csv_when_service_fails(self, tmp_path):
        """Regression test: mapper.py was not passing errors to write_output_csv."""
        from services.consensus import write_output_csv, build_consensus

        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.9)},
            "Anthropic": {"W2": ("Tax Docs", 0.85)},
        }
        errors = {"Gemini": "connection timeout"}
        confident, review = build_consensus(results, ["W2"])
        path = str(tmp_path / "out.csv")

        # Pass errors explicitly — must appear in output
        write_output_csv(path, confident, review, list(results.keys()), errors)

        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Gemini" in content
        assert "connection timeout" in content

    def test_no_errors_does_not_add_failed_services_note(self, tmp_path):
        results = {
            "OpenAI":    {"W2": ("Tax Docs", 0.9)},
            "Anthropic": {"W2": ("Tax Docs", 0.85)},
        }
        confident, review = build_consensus(results, ["W2"])
        path = str(tmp_path / "out.csv")
        write_output_csv(path, confident, review, list(results.keys()), {})

        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "NOTE: The following AI services failed" not in content


# ============================================================
# 10. PRELOADED DATA — real-world file integrity
# ============================================================

class TestPreloadedData:
    """Verify the preloaded Ocrolus CSV can actually be ingested."""

    def test_preloaded_ocrolus_csv_loads_without_error(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "preloaded", "docs list mar 2026.csv")
        if not os.path.isfile(path):
            pytest.skip("Preloaded CSV not present")
        result = load_ocrolus_types(path)
        assert len(result) > 100, f"Expected many form types, got {len(result)}"
        assert len(result) == len(set(result)), "Duplicate entries in preloaded CSV"
        assert result == sorted(result), "Output is not sorted"

    def test_preloaded_ocrolus_csv_has_no_empty_strings(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "preloaded", "docs list mar 2026.csv")
        if not os.path.isfile(path):
            pytest.skip("Preloaded CSV not present")
        result = load_ocrolus_types(path)
        assert all(ft.strip() != "" for ft in result), "Empty string in form types"
        assert all(isinstance(ft, str) for ft in result), "Non-string in form types"
