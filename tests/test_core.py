"""
Tests for FileTag core module.

These tests use a mock xattr backend to avoid requiring actual xattr filesystem
support. We patch the xattr module at the test level.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from filetag.core import (
    TAG_SEPARATOR,
    XATTR_KEY,
    FileTagNotFoundError,
    TagValidationError,
    XAttrNotAvailableError,
    XAttrNotSupportedError,
    _read_tags_raw,
    _write_tags_raw,
    _remove_xattr,
    add_tags,
    clear_tags,
    export_tags,
    find_by_tag,
    get_stats,
    get_tags,
    import_tags,
    list_all_tags,
    remove_tags,
    set_tags,
    validate_tag,
)


# ---------------------------------------------------------------------------
# Helpers for setting up mock xattr
# ---------------------------------------------------------------------------

class MockXAttr:
    """In-memory mock for xattr operations on a virtual filesystem."""

    def __init__(self):
        self._attrs: dict = {}  # path -> {key: value}

    def getxattr(self, path: str, key: str):
        attrs = self._attrs.get(path, {})
        val = attrs.get(key)
        if val is not None:
            return val.encode("utf-8") if isinstance(val, str) else val
        raise OSError(93, "Attribute not found")

    def setxattr(self, path: str, key: str, value: bytes):
        self._attrs.setdefault(path, {})[key] = value.decode("utf-8") if isinstance(value, bytes) else value

    def removexattr(self, path: str, key: str):
        if path in self._attrs and key in self._attrs[path]:
            del self._attrs[path][key]


@pytest.fixture
def mock_xattr():
    """Fixture that provides a MockXAttr and patches the xattr module."""
    mock = MockXAttr()
    with patch("filetag.core.xattr") as mock_mod:
        mock_mod.getxattr = mock.getxattr
        mock_mod.setxattr = mock.setxattr
        mock_mod.removexattr = mock.removexattr
        yield mock


@pytest.fixture
def temp_files():
    """Create temporary files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        files = {
            "a.txt": base / "a.txt",
            "b.txt": base / "b.txt",
            "c.py": base / "c.py",
            "sub/d.txt": base / "sub" / "d.txt",
            "sub/e.py": base / "sub" / "e.py",
        }
        for name, path in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"content of {name}")
        yield base, files


# ---------------------------------------------------------------------------
# Tests for validate_tag
# ---------------------------------------------------------------------------


class TestValidateTag:
    def test_valid_tags(self):
        assert validate_tag("important") == "important"
        assert validate_tag("Work") == "work"
        assert validate_tag("my-tag") == "my-tag"
        assert validate_tag("under_score") == "under_score"
        assert validate_tag("tag.name") == "tag.name"
        assert validate_tag("  padded  ") == "padded"
        assert validate_tag("a" * 64) == "a" * 64

    def test_empty_tag(self):
        with pytest.raises(TagValidationError, match="cannot be empty"):
            validate_tag("")

    def test_invalid_tag_chars(self):
        with pytest.raises(TagValidationError, match="Invalid"):
            validate_tag("bad tag!")  # space and exclamation
        with pytest.raises(TagValidationError, match="Invalid"):
            validate_tag("tag@name")
        with pytest.raises(TagValidationError, match="Invalid"):
            validate_tag("tag/name")

    def test_too_long_tag(self):
        with pytest.raises(TagValidationError, match="too long"):
            validate_tag("a" * 65)


# ---------------------------------------------------------------------------
# Tests for core operations (with mock xattr)
# ---------------------------------------------------------------------------


class TestCoreOperations:
    def test_get_tags_empty(self, mock_xattr, temp_files):
        base, files = temp_files
        tags = get_tags(files["a.txt"])
        assert tags == set()

    def test_add_tags(self, mock_xattr, temp_files):
        base, files = temp_files
        result = add_tags(files["a.txt"], ["important", "work"])
        assert result == {"important", "work"}

        # Verify persistence
        tags = get_tags(files["a.txt"])
        assert tags == {"important", "work"}

    def test_add_tags_duplicates(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "important", "work"])
        tags = get_tags(files["a.txt"])
        assert tags == {"important", "work"}

    def test_add_tags_multiple_calls(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        add_tags(files["a.txt"], ["work", "urgent"])
        tags = get_tags(files["a.txt"])
        assert tags == {"important", "urgent", "work"}

    def test_remove_tags(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work", "urgent"])
        result = remove_tags(files["a.txt"], ["work"])
        assert result == {"important", "urgent"}

        tags = get_tags(files["a.txt"])
        assert tags == {"important", "urgent"}

    def test_remove_all_tags_clears_xattr(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        result = remove_tags(files["a.txt"], ["important"])
        assert result == set()
        tags = get_tags(files["a.txt"])
        assert tags == set()

    def test_clear_tags(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        clear_tags(files["a.txt"])
        tags = get_tags(files["a.txt"])
        assert tags == set()

    def test_set_tags(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        result = set_tags(files["a.txt"], ["new", "tags"])
        assert result == {"new", "tags"}
        tags = get_tags(files["a.txt"])
        assert tags == {"new", "tags"}

    def test_set_tags_empty_clears(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        set_tags(files["a.txt"], [])
        tags = get_tags(files["a.txt"])
        assert tags == set()


# ---------------------------------------------------------------------------
# Tests for find_by_tag
# ---------------------------------------------------------------------------


class TestFindByTag:
    def test_find_single_tag(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        add_tags(files["b.txt"], ["work"])
        add_tags(files["c.py"], ["python"])

        results = find_by_tag([base], ["important"])
        assert len(results) == 1
        assert results[0][0] == files["a.txt"].resolve()

        results = find_by_tag([base], ["work"])
        assert len(results) == 2

    def test_find_any_tag(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        add_tags(files["b.txt"], ["work"])

        results = find_by_tag([base], ["important", "work"], match_all=False)
        assert len(results) == 2

    def test_find_all_tags(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        add_tags(files["b.txt"], ["work"])

        results = find_by_tag([base], ["important", "work"], match_all=True)
        assert len(results) == 1
        assert results[0][0] == files["a.txt"].resolve()

    def test_find_no_match(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        results = find_by_tag([base], ["nonexistent"])
        assert len(results) == 0

    def test_find_recursive(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["sub/d.txt"], ["hidden"])
        results = find_by_tag([base], ["hidden"], recursive=True)
        assert len(results) == 1
        assert results[0][0] == files["sub/d.txt"].resolve()

        results = find_by_tag([base], ["hidden"], recursive=False)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Tests for list_all_tags
# ---------------------------------------------------------------------------


class TestListAllTags:
    def test_list_all(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        add_tags(files["b.txt"], ["work"])

        tag_map = list_all_tags([base])
        assert set(tag_map.keys()) == {"important", "work"}
        assert len(tag_map["important"]) == 1
        assert len(tag_map["work"]) == 2

    def test_list_empty(self, mock_xattr, temp_files):
        base, files = temp_files
        tag_map = list_all_tags([base])
        assert tag_map == {}


# ---------------------------------------------------------------------------
# Tests for export / import
# ---------------------------------------------------------------------------


class TestExportImport:
    def test_export(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        add_tags(files["b.txt"], ["work"])

        data = export_tags([base])
        assert str(files["a.txt"].resolve()) in data
        assert str(files["b.txt"].resolve()) in data
        assert data[str(files["a.txt"].resolve())] == ["important", "work"]
        assert data[str(files["b.txt"].resolve())] == ["work"]

    def test_export_empty(self, mock_xattr, temp_files):
        base, files = temp_files
        data = export_tags([base])
        assert data == {}

    def test_import(self, mock_xattr, temp_files):
        base, files = temp_files
        data = {
            str(files["a.txt"].resolve()): ["new", "tags"],
            str(files["b.txt"].resolve()): ["other"],
        }
        success, errors = import_tags(data)
        assert success == 2
        assert errors == 0

        assert get_tags(files["a.txt"]) == {"new", "tags"}
        assert get_tags(files["b.txt"]) == {"other"}

    def test_import_with_errors(self, mock_xattr, temp_files):
        base, files = temp_files
        data = {
            str(files["a.txt"].resolve()): ["tag1"],
            "/nonexistent/path.txt": ["tag2"],
        }
        success, errors = import_tags(data)
        assert success == 1
        assert errors == 1


# ---------------------------------------------------------------------------
# Tests for stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_basic(self, mock_xattr, temp_files):
        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        add_tags(files["b.txt"], ["work"])
        add_tags(files["c.py"], ["python"])

        stats = get_stats([base])
        assert stats["total_files"] >= 3
        assert stats["tagged_files"] == 3
        assert stats["total_tags"] == 3
        top_tags = {t["tag"]: t["count"] for t in stats["top_tags"]}
        assert top_tags["work"] == 2

    def test_stats_no_tags(self, mock_xattr, temp_files):
        base, files = temp_files
        stats = get_stats([base])
        assert stats["total_files"] >= 3
        assert stats["tagged_files"] == 0
        assert stats["total_tags"] == 0


# ---------------------------------------------------------------------------
# Tests for error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_file_not_found(self, temp_files):
        base, files = temp_files
        nonexistent = base / "nonexistent.txt"
        with pytest.raises(FileTagNotFoundError):
            get_tags(nonexistent)

    def test_invalid_tag_on_add(self, mock_xattr, temp_files):
        base, files = temp_files
        with pytest.raises(TagValidationError):
            add_tags(files["a.txt"], ["invalid tag!"])

    def test_xattr_not_available(self, temp_files):
        base, files = temp_files
        with patch("filetag.core._HAS_XATTR", False):
            with pytest.raises(XAttrNotAvailableError):
                get_tags(files["a.txt"])

    def test_xattr_not_supported(self, temp_files):
        base, files = temp_files
        with patch("filetag.core.xattr") as mock_mod:
            def fail_setxattr(*args, **kwargs):
                raise OSError(95, "Operation not supported")
            mock_mod.setxattr = fail_setxattr
            with pytest.raises(XAttrNotSupportedError):
                add_tags(files["a.txt"], ["tag"])


# ---------------------------------------------------------------------------
# Tests for CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_help(self):
        from click.testing import CliRunner
        from filetag.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "FileTag" in result.output

    def test_cli_add(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        runner = CliRunner()
        result = runner.invoke(main, ["add", str(files["a.txt"]), "-t", "important", "-t", "work"])
        assert result.exit_code == 0, result.output
        assert "important" in result.output
        assert "work" in result.output

    def test_cli_list(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        runner = CliRunner()
        result = runner.invoke(main, ["list", str(files["a.txt"])])
        assert result.exit_code == 0
        assert "important" in result.output
        assert "work" in result.output

    def test_cli_find(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        runner = CliRunner()
        result = runner.invoke(main, ["find", "important", "--path", str(base)])
        assert result.exit_code == 0
        assert "a.txt" in result.output

    def test_cli_stats(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        runner = CliRunner()
        result = runner.invoke(main, ["stats", "--path", str(base)])
        assert result.exit_code == 0
        assert "Statistics" in result.output or "tagged" in result.output

    def test_cli_export_import(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        add_tags(files["a.txt"], ["important"])

        runner = CliRunner()
        result = runner.invoke(main, ["export", "--path", str(base)])
        assert result.exit_code == 0
        exported = json.loads(result.output)
        assert str(files["a.txt"].resolve()) in exported

    def test_cli_remove(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        add_tags(files["a.txt"], ["important", "work"])
        runner = CliRunner()
        result = runner.invoke(main, ["remove", str(files["a.txt"]), "-t", "work"])
        assert result.exit_code == 0, result.output
        assert "important" in result.output

    def test_cli_clear(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        runner = CliRunner()
        result = runner.invoke(main, ["clear", str(files["a.txt"])])
        assert result.exit_code == 0
        assert "Cleared" in result.output

    def test_cli_show(self, mock_xattr, temp_files):
        from click.testing import CliRunner
        from filetag.cli import main

        base, files = temp_files
        add_tags(files["a.txt"], ["important"])
        runner = CliRunner()
        result = runner.invoke(main, ["show", "--path", str(base)])
        assert result.exit_code == 0
        assert "important" in result.output