"""Tests for AI service response parsing (no API calls needed)."""

import json
import importlib

import pytest


FORM_TYPES = ["W-2", "Pay Stub"]


class TestOpenAIParsing:
    def setup_method(self):
        mod = importlib.import_module("services.ai_openai")
        self.parse = mod._parse_response

    def test_valid_json_with_confidence(self):
        raw = json.dumps({
            "W-2": {"container": "Tax Docs", "confidence": 0.95},
            "Pay Stub": {"container": "Income", "confidence": 0.85},
        })
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == ("Tax Docs", 0.95)
        assert result["Pay Stub"] == ("Income", 0.85)

    def test_plain_string_fallback(self):
        raw = json.dumps({"W-2": "Tax Docs", "Pay Stub": "Income"})
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == ("Tax Docs", 0.5)
        assert result["Pay Stub"] == ("Income", 0.5)

    def test_missing_key_becomes_no_match(self):
        raw = json.dumps({"W-2": {"container": "Tax Docs", "confidence": 0.9}})
        result = self.parse(raw, FORM_TYPES)
        assert result["Pay Stub"] == ("NO_MATCH", 0.0)

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            self.parse("not json", FORM_TYPES)

    def test_confidence_clamped(self):
        raw = json.dumps({"W-2": {"container": "Tax Docs", "confidence": 1.5}, "Pay Stub": {"container": "Income", "confidence": -0.1}})
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"][1] == 1.0
        assert result["Pay Stub"][1] == 0.0


class TestAnthropicParsing:
    def setup_method(self):
        mod = importlib.import_module("services.ai_anthropic")
        self.parse = mod._parse_response

    def test_valid_json_with_confidence(self):
        raw = json.dumps({
            "W-2": {"container": "Tax Docs", "confidence": 0.9},
            "Pay Stub": {"container": "Income", "confidence": 0.8},
        })
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == ("Tax Docs", 0.9)

    def test_strips_markdown_fences(self):
        inner = json.dumps({
            "W-2": {"container": "Tax Docs", "confidence": 0.9},
            "Pay Stub": {"container": "Income", "confidence": 0.8},
        })
        raw = f"```json\n{inner}\n```"
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == ("Tax Docs", 0.9)

    def test_missing_key_becomes_no_match(self):
        raw = json.dumps({"W-2": {"container": "Tax Docs", "confidence": 0.9}})
        result = self.parse(raw, FORM_TYPES)
        assert result["Pay Stub"] == ("NO_MATCH", 0.0)


class TestGeminiParsing:
    def setup_method(self):
        mod = importlib.import_module("services.ai_gemini")
        self.parse = mod._parse_response

    def test_valid_json_with_confidence(self):
        raw = json.dumps({
            "W-2": {"container": "Tax Docs", "confidence": 0.92},
            "Pay Stub": {"container": "Income", "confidence": 0.88},
        })
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == ("Tax Docs", 0.92)

    def test_plain_string_fallback(self):
        raw = json.dumps({"W-2": "Tax Docs", "Pay Stub": "Income"})
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == ("Tax Docs", 0.5)

    def test_missing_key_becomes_no_match(self):
        raw = json.dumps({"W-2": {"container": "Tax Docs", "confidence": 0.9}})
        result = self.parse(raw, FORM_TYPES)
        assert result["Pay Stub"] == ("NO_MATCH", 0.0)

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            self.parse("not json", FORM_TYPES)
