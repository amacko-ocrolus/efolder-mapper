"""Tests for the consensus engine."""

import csv
import os

from services.consensus import build_consensus, write_output_csv


class TestBuildConsensus:
    def test_all_agree(self):
        results = {
            "OpenAI":    {"W-2": ("Tax Documents", 0.95)},
            "Anthropic": {"W-2": ("Tax Documents", 0.90)},
            "Gemini":    {"W-2": ("Tax Documents", 0.92)},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 1
        assert len(review) == 0
        assert confident[0]["suggested_container"] == "Tax Documents"

    def test_two_agree(self):
        results = {
            "OpenAI":    {"W-2": ("Tax Documents", 0.95)},
            "Anthropic": {"W-2": ("Tax Documents", 0.90)},
            "Gemini":    {"W-2": ("Tax Forms", 0.60)},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 1
        assert confident[0]["suggested_container"] == "Tax Documents"
        assert "OpenAI" in confident[0]["agreed_services"]
        assert "Anthropic" in confident[0]["agreed_services"]

    def test_avg_confidence_calculated(self):
        results = {
            "OpenAI":    {"W-2": ("Tax Documents", 0.80)},
            "Anthropic": {"W-2": ("Tax Documents", 0.60)},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert confident[0]["avg_confidence"] == 0.70

    def test_no_consensus(self):
        results = {
            "OpenAI":    {"W-2": ("Tax Documents", 0.70)},
            "Anthropic": {"W-2": ("Tax Forms", 0.65)},
            "Gemini":    {"W-2": ("IRS Docs", 0.50)},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 0
        assert len(review) == 1
        assert review[0]["OpenAI_suggestion"] == "Tax Documents"

    def test_best_guess_is_highest_confidence(self):
        results = {
            "OpenAI":    {"W-2": ("Tax Documents", 0.90)},
            "Anthropic": {"W-2": ("Tax Forms", 0.40)},
            "Gemini":    {"W-2": ("IRS Docs", 0.50)},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert review[0]["best_guess"] == "Tax Documents"
        assert review[0]["best_guess_service"] == "OpenAI"

    def test_no_match_consensus_goes_to_review(self):
        results = {
            "OpenAI":    {"W-2": ("NO_MATCH", 0.0)},
            "Anthropic": {"W-2": ("NO_MATCH", 0.0)},
            "Gemini":    {"W-2": ("NO_MATCH", 0.0)},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 0
        assert len(review) == 1

    def test_mixed_types(self):
        results = {
            "OpenAI":    {"W-2": ("Tax Docs", 0.9), "Pay Stub": ("Income", 0.8)},
            "Anthropic": {"W-2": ("Tax Docs", 0.85), "Pay Stub": ("Earnings", 0.7)},
            "Gemini":    {"W-2": ("Tax Forms", 0.6), "Pay Stub": ("Income", 0.75)},
        }
        confident, review = build_consensus(results, ["W-2", "Pay Stub"])
        assert len(confident) == 2
        assert len(review) == 0


class TestWriteOutputCSV:
    def test_writes_valid_csv(self, tmp_path):
        confident = [
            {
                "ocrolus_type": "W-2",
                "suggested_container": "Tax Documents",
                "agreed_services": "OpenAI, Anthropic",
                "avg_confidence": 0.92,
            }
        ]
        review = [
            {
                "ocrolus_type": "Pay Stub",
                "best_guess": "Income",
                "best_confidence": 0.70,
                "best_guess_service": "OpenAI",
                "OpenAI_suggestion": "Income",
                "OpenAI_confidence": 0.70,
                "Anthropic_suggestion": "Earnings",
                "Anthropic_confidence": 0.55,
            }
        ]
        path = os.path.join(tmp_path, "output.csv")
        write_output_csv(path, confident, review, ["OpenAI", "Anthropic"])

        with open(path) as f:
            content = f.read()

        assert "CONFIDENT MAPPINGS" in content
        assert "MANUAL REVIEW" in content
        assert "W-2" in content
        assert "Pay Stub" in content
        assert "0.92" in content
