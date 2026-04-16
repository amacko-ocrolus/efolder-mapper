"""Tests for the file ingestion module."""

import json
import os
import tempfile

import pytest

from services.ingestion import load_attachment_names, load_lender_containers, load_ocrolus_types


# ---------------------------------------------------------------------------
# Ocrolus CSV loading
# ---------------------------------------------------------------------------


def _write_csv(tmp_dir, filename, content):
    path = os.path.join(tmp_dir, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


class TestLoadOcrolusTypes:
    def test_single_column(self, tmp_path):
        path = _write_csv(tmp_path, "types.csv", "Form Type\nW-2\nPay Stub\nW-2\n")
        result = load_ocrolus_types(path)
        assert result == ["Pay Stub", "W-2"]

    def test_auto_detect_column(self, tmp_path):
        path = _write_csv(
            tmp_path, "types.csv", "id,form_name,other\n1,W-2,x\n2,1099,y\n"
        )
        result = load_ocrolus_types(path)
        assert "W-2" in result
        assert "1099" in result

    def test_deduplicates_and_sorts(self, tmp_path):
        path = _write_csv(tmp_path, "types.csv", "name\nB\nA\nB\nC\n")
        assert load_ocrolus_types(path) == ["A", "B", "C"]

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_ocrolus_types("/nonexistent/file.csv")

    def test_empty_data_raises(self, tmp_path):
        path = _write_csv(tmp_path, "types.csv", "name\n")
        with pytest.raises(ValueError, match="No form type names"):
            load_ocrolus_types(path)

    def test_no_headers_raises(self, tmp_path):
        path = os.path.join(tmp_path, "empty.csv")
        with open(path, "w") as f:
            f.write("")
        with pytest.raises(ValueError, match="no headers"):
            load_ocrolus_types(path)


# ---------------------------------------------------------------------------
# Lender container loading — CSV
# ---------------------------------------------------------------------------


class TestLoadLenderContainersCSV:
    def test_single_column(self, tmp_path):
        path = _write_csv(tmp_path, "containers.csv", "Container\nTax Docs\nAssets\n")
        result = load_lender_containers(path)
        assert result == ["Assets", "Tax Docs"]

    def test_auto_detect_column(self, tmp_path):
        path = _write_csv(
            tmp_path, "containers.csv", "id,container_name\n1,Tax Docs\n2,Assets\n"
        )
        result = load_lender_containers(path)
        assert "Tax Docs" in result

    def test_unsupported_extension_raises(self, tmp_path):
        path = _write_csv(tmp_path, "containers.xml", "<data/>")
        with pytest.raises(ValueError, match="Unsupported"):
            load_lender_containers(path)


# ---------------------------------------------------------------------------
# Lender container loading — JSON
# ---------------------------------------------------------------------------


class TestLoadLenderContainersJSON:
    def _write_json(self, tmp_path, data):
        path = os.path.join(tmp_path, "containers.json")
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_flat_array(self, tmp_path):
        path = self._write_json(tmp_path, ["Tax Docs", "Assets", "Income"])
        result = load_lender_containers(path)
        assert result == ["Assets", "Income", "Tax Docs"]

    def test_array_of_objects(self, tmp_path):
        path = self._write_json(
            tmp_path, [{"name": "Tax Docs"}, {"name": "Assets"}]
        )
        result = load_lender_containers(path)
        assert "Tax Docs" in result

    def test_nested_object_with_array(self, tmp_path):
        path = self._write_json(
            tmp_path, {"containers": ["Tax Docs", "Assets"]}
        )
        result = load_lender_containers(path)
        assert result == ["Assets", "Tax Docs"]

    def test_empty_json_raises(self, tmp_path):
        path = self._write_json(tmp_path, [])
        with pytest.raises(ValueError, match="No container names"):
            load_lender_containers(path)


class TestLoadAttachmentNames:
    def test_loads_form_type_to_attachment_name(self, tmp_path):
        path = _write_csv(tmp_path, "table-data.csv",
            "Form Type,Container Name,Attachment Name,other\nW2,Tax Returns,Wage and Tax Statement,x\nA_1040,Tax Returns,1040 Return,y\n")
        result = load_attachment_names(path)
        assert result["W2"] == "Wage and Tax Statement"
        assert result["A_1040"] == "1040 Return"

    def test_missing_file_returns_empty(self):
        assert load_attachment_names("/nonexistent/table-data.csv") == {}

    def test_strips_whitespace(self, tmp_path):
        path = _write_csv(tmp_path, "table-data.csv",
            "Form Type,Container Name,Attachment Name\n W2 ,Tax Returns, Wage and Tax Statement \n")
        result = load_attachment_names(path)
        assert result.get("W2") == "Wage and Tax Statement"
