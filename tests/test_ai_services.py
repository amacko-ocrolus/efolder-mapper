"""Tests for AI service response parsing (no API calls needed)."""

import json
import importlib

import pytest


FORM_TYPES = ["W-2", "Pay Stub"]


class TestOpenAIParsing:
    def setup_method(self):
        mod = importlib.import_module("services.ai_openai")
        self.parse = mod._parse_response

    def test_valid_json(self):
        raw = json.dumps({"W-2": "Tax Docs", "Pay Stub": "Income"})
        result = self.parse(raw, FORM_TYPES)
        assert result == {"W-2": "Tax Docs", "Pay Stub": "Income"}

    def test_missing_key_becomes_no_match(self):
        raw = json.dumps({"W-2": "Tax Docs"})
        result = self.parse(raw, FORM_TYPES)
        assert result["Pay Stub"] == "NO_MATCH"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            self.parse("not json", FORM_TYPES)


class TestAnthropicParsing:
    def setup_method(self):
        mod = importlib.import_module("services.ai_anthropic")
        self.parse = mod._parse_response

    def test_valid_json(self):
        raw = json.dumps({"W-2": "Tax Docs", "Pay Stub": "Income"})
        result = self.parse(raw, FORM_TYPES)
        assert result == {"W-2": "Tax Docs", "Pay Stub": "Income"}

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps({"W-2": "Tax Docs", "Pay Stub": "Income"}) + "\n```"
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == "Tax Docs"


class TestOllamaParsing:
    def setup_method(self):
        mod = importlib.import_module("services.ai_ollama")
        self.parse = mod._parse_response

    def test_valid_json(self):
        raw = json.dumps({"W-2": "Tax Docs", "Pay Stub": "Income"})
        result = self.parse(raw, FORM_TYPES)
        assert result == {"W-2": "Tax Docs", "Pay Stub": "Income"}

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps({"W-2": "Tax Docs", "Pay Stub": "Income"}) + "\n```"
        result = self.parse(raw, FORM_TYPES)
        assert result["W-2"] == "Tax Docs"
