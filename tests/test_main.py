"""Tests for main module (send_result_file)."""
import os

import pytest

import main as main_mod
from main import send_result_file


class TestSendResultFile:
    """Tests for send_result_file."""

    def test_returns_false_when_no_file(self):
        success, filename = send_result_file(None)
        assert success is False
        assert filename is None

    def test_returns_false_when_file_does_not_exist(self):
        success, filename = send_result_file("/nonexistent/path/file.hotb")
        assert success is False
        assert filename is None

    def test_returns_false_when_client_path_unset(self, tmp_path, monkeypatch):
        hotb = tmp_path / "measurement_results_20250129_120000.hotb"
        hotb.write_text("dummy")
        monkeypatch.setattr(main_mod, "CLIENT_PATH", None)
        success, filename = send_result_file(str(hotb))
        assert success is False
        assert filename is None

    def test_copies_and_returns_filename_when_success(self, tmp_path, monkeypatch):
        client_path = tmp_path / "client_results"
        client_path.mkdir()
        monkeypatch.setattr(main_mod, "CLIENT_PATH", str(client_path))

        hotb = tmp_path / "measurement_results_20250129_120000.hotb"
        hotb.write_text("<?xml version='1.0'?><test/>")

        success, result_filename = send_result_file(str(hotb))

        assert success is True
        assert result_filename == "Result_20250129_120000.hotb"
        dest = client_path / result_filename
        assert dest.exists()
        assert dest.read_text() == "<?xml version='1.0'?><test/>"
