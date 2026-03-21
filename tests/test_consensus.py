"""Tests for the consensus engine."""

import csv
import os

from services.consensus import build_consensus, write_output_csv


class TestBuildConsensus:
    def test_all_agree(self):
        results = {
            "OpenAI": {"W-2": "Tax Documents"},
            "Anthropic": {"W-2": "Tax Documents"},
            "Google": {"W-2": "Tax Documents"},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 1
        assert len(review) == 0
        assert confident[0]["suggested_container"] == "Tax Documents"

    def test_two_agree(self):
        results = {
            "OpenAI": {"W-2": "Tax Documents"},
            "Anthropic": {"W-2": "Tax Documents"},
            "Google": {"W-2": "Tax Forms"},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 1
        assert confident[0]["suggested_container"] == "Tax Documents"
        assert "OpenAI" in confident[0]["agreed_services"]
        assert "Anthropic" in confident[0]["agreed_services"]

    def test_no_consensus(self):
        results = {
            "OpenAI": {"W-2": "Tax Documents"},
            "Anthropic": {"W-2": "Tax Forms"},
            "Google": {"W-2": "IRS Docs"},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 0
        assert len(review) == 1
        assert review[0]["OpenAI_suggestion"] == "Tax Documents"

    def test_no_match_consensus_goes_to_review(self):
        results = {
            "OpenAI": {"W-2": "NO_MATCH"},
            "Anthropic": {"W-2": "NO_MATCH"},
            "Google": {"W-2": "NO_MATCH"},
        }
        confident, review = build_consensus(results, ["W-2"])
        assert len(confident) == 0
        assert len(review) == 1

    def test_mixed_types(self):
        results = {
            "OpenAI": {"W-2": "Tax Docs", "Pay Stub": "Income"},
            "Anthropic": {"W-2": "Tax Docs", "Pay Stub": "Earnings"},
            "Google": {"W-2": "Tax Forms", "Pay Stub": "Income"},
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
            }
        ]
        review = [
            {
                "ocrolus_type": "Pay Stub",
                "OpenAI_suggestion": "Income",
                "Anthropic_suggestion": "Earnings",
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
