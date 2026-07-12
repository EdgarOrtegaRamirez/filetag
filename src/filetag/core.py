"""
Core module for FileTag - manages file tagging via filesystem extended attributes.

Uses the xattr library to read/write extended attributes on files.
Tags are stored in a single xattr key "user.filetag.tags" as a comma-separated
list. This keeps the implementation simple and avoids excessive attribute writes.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# xattr is an optional dependency; we handle ImportError gracefully
try:
    import xattr  # type: ignore[import-untyped]

    _HAS_XATTR = True
except ImportError:
    _HAS_XATTR = False

# The xattr key used to store tags (Linux namespace)
XATTR_KEY = "user.filetag.tags"
# Separator used inside the xattr value
TAG_SEPARATOR = ","
# Regex for valid tag names: alphanumeric, hyphens, underscores, dots
VALID_TAG_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


class FileTagError(Exception):
    """Base exception for FileTag operations."""


class XAttrNotAvailableError(FileTagError):
    """Raised when the xattr library is not available."""


class TagValidationError(FileTagError):
    """Raised when a tag name is invalid."""


class FileTagNotFoundError(FileTagError):
    """Raised when the target file does not exist."""


class XAttrNotSupportedError(FileTagError):
    """Raised when the filesystem does not support extended attributes."""


def _check_xattr() -> None:
    """Verify xattr library is available."""
    if not _HAS_XATTR:
        raise XAttrNotAvailableError(
            "The 'xattr' library is not installed. Install it with: pip install xattr"
        )


def _check_file(path: Path) -> None:
    """Verify the file exists and is a regular file or directory."""
    if not path.exists():
        raise FileTagNotFoundError(f"Path does not exist: {path}")
    if not path.is_file() and not path.is_dir():
        raise FileTagError(f"Path is not a regular file or directory: {path}")


def validate_tag(tag: str) -> str:
    """
    Validate a tag name.

    Args:
        tag: The tag name to validate.

    Returns:
        The validated tag name (lowercased).

    Raises:
        TagValidationError: If the tag name is invalid.
    """
    tag = tag.strip().lower()
    if not tag:
        raise TagValidationError("Tag name cannot be empty")
    if len(tag) > 64:
        raise TagValidationError(f"Tag name too long (max 64 chars): {tag}")
    if not VALID_TAG_RE.match(tag):
        raise TagValidationError(
            f"Invalid tag name: '{tag}'. Tags may only contain "
            f"letters, numbers, hyphens, underscores, and dots."
        )
    return tag


def _read_tags_raw(path: str) -> str | None:
    """
    Read the raw tag string from xattr.

    Args:
        path: Filesystem path to read from.

    Returns:
        The raw tag string, or None if no tags are set.
    """
    _check_xattr()
    try:
        value = xattr.getxattr(path, XATTR_KEY)  # type: ignore[arg-type]
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)
    except OSError as e:
        # ENOATTR / ENODATA means no attribute set
        if hasattr(e, "errno") and e.errno in (61, 93):  # ENODATA on Linux, ENOATTR on macOS
            return None
        if hasattr(e, "errno") and e.errno == 95:  # EOPNOTSUPP
            raise XAttrNotSupportedError(
                f"Extended attributes not supported on this filesystem: {path}"
            ) from e
        raise FileTagError(f"Failed to read xattr from {path}: {e}") from e


def _write_tags_raw(path: str, tags_str: str) -> None:
    """
    Write the raw tag string to xattr.

    Args:
        path: Filesystem path to write to.
        tags_str: Comma-separated tag string.
    """
    _check_xattr()
    try:
        xattr.setxattr(path, XATTR_KEY, tags_str.encode("utf-8"))  # type: ignore[arg-type]
    except OSError as e:
        if hasattr(e, "errno") and e.errno == 95:  # EOPNOTSUPP
            raise XAttrNotSupportedError(
                f"Extended attributes not supported on this filesystem: {path}"
            ) from e
        raise FileTagError(f"Failed to write xattr to {path}: {e}") from e


def _remove_xattr(path: str) -> None:
    """Remove the tag xattr from a file."""
    _check_xattr()
    try:
        xattr.removexattr(path, XATTR_KEY)  # type: ignore[arg-type]
    except OSError as e:
        if hasattr(e, "errno") and e.errno in (61, 93):
            return  # No attribute to remove is fine
        if hasattr(e, "errno") and e.errno == 95:
            raise XAttrNotSupportedError(
                f"Extended attributes not supported on this filesystem: {path}"
            ) from e
        raise FileTagError(f"Failed to remove xattr from {path}: {e}") from e


def get_tags(path: Path) -> set[str]:
    """
    Get the set of tags for a file.

    Args:
        path: Path to the file.

    Returns:
        Set of tag strings (empty if no tags).
    """
    _check_file(path)
    raw = _read_tags_raw(str(path))
    if raw is None or raw.strip() == "":
        return set()
    return {t.strip() for t in raw.split(TAG_SEPARATOR) if t.strip()}


def add_tags(path: Path, tags: list[str]) -> set[str]:
    """
    Add tags to a file. Duplicates are ignored.

    Args:
        path: Path to the file.
        tags: List of tag names to add.

    Returns:
        The updated set of tags.
    """
    _check_file(path)
    validated = [validate_tag(t) for t in tags]
    current = get_tags(path)
    current.update(validated)
    _write_tags_raw(str(path), TAG_SEPARATOR.join(sorted(current)))
    return current


def remove_tags(path: Path, tags: list[str]) -> set[str]:
    """
    Remove tags from a file.

    Args:
        path: Path to the file.
        tags: List of tag names to remove.

    Returns:
        The updated set of tags.
    """
    _check_file(path)
    validated = [validate_tag(t) for t in tags]
    current = get_tags(path)
    for t in validated:
        current.discard(t)
    if current:
        _write_tags_raw(str(path), TAG_SEPARATOR.join(sorted(current)))
    else:
        _remove_xattr(str(path))
    return current


def clear_tags(path: Path) -> None:
    """
    Remove all tags from a file.

    Args:
        path: Path to the file.
    """
    _check_file(path)
    _remove_xattr(str(path))


def set_tags(path: Path, tags: list[str]) -> set[str]:
    """
    Replace all tags on a file with a new set.

    Args:
        path: Path to the file.
        tags: List of tag names to set.

    Returns:
        The new set of tags.
    """
    _check_file(path)
    validated = {validate_tag(t) for t in tags}
    if validated:
        _write_tags_raw(str(path), TAG_SEPARATOR.join(sorted(validated)))
    else:
        _remove_xattr(str(path))
    return validated


def find_by_tag(
    search_paths: list[Path],
    tags: list[str],
    *,
    match_all: bool = False,
    recursive: bool = True,
) -> list[tuple[Path, set[str]]]:
    """
    Find files matching given tags.

    Args:
        search_paths: Directories to search.
        tags: Tags to match.
        match_all: If True, files must have ALL specified tags.
                    If False, any tag match is sufficient.
        recursive: If True, search recursively into subdirectories.

    Returns:
        List of (path, tags) tuples for matching files.
    """
    _check_xattr()
    validated = {validate_tag(t) for t in tags}
    results: list[tuple[Path, set[str]]] = []

    for base_path in search_paths:
        if not base_path.exists():
            continue
        if base_path.is_file():
            file_tags = get_tags(base_path)
            if _matches(file_tags, validated, match_all):
                results.append((base_path.resolve(), file_tags))
        elif base_path.is_dir():
            if recursive:
                for dirpath, _dirnames, filenames in os.walk(str(base_path)):
                    for fname in filenames:
                        fpath = Path(os.path.join(dirpath, fname))
                        try:
                            if os.path.islink(str(fpath)):
                                continue
                            file_tags = get_tags(fpath)
                            if _matches(file_tags, validated, match_all):
                                results.append((fpath.resolve(), file_tags))
                        except (FileTagError, OSError):
                            continue
            else:
                for entry in os.scandir(str(base_path)):
                    if entry.is_file() and not entry.is_symlink():
                        fpath = Path(entry.path)
                        try:
                            file_tags = get_tags(fpath)
                            if _matches(file_tags, validated, match_all):
                                results.append((fpath.resolve(), file_tags))
                        except (FileTagError, OSError):
                            continue

    return results


def _matches(file_tags: set[str], query_tags: set[str], match_all: bool) -> bool:
    """Check if file_tags match query_tags based on match_all flag."""
    if not file_tags or not query_tags:
        return False
    if match_all:
        return query_tags.issubset(file_tags)
    return bool(query_tags & file_tags)


def list_all_tags(search_paths: list[Path], recursive: bool = True) -> dict[str, list[Path]]:
    """
    List all tags found across files in the given paths.

    Args:
        search_paths: Directories to scan.
        recursive: If True, scan recursively.

    Returns:
        Dictionary mapping tag names to lists of file paths.
    """
    tag_map: dict[str, list[Path]] = {}
    for base_path in search_paths:
        if not base_path.exists():
            continue
        if base_path.is_file():
            _accumulate_tags(base_path, tag_map)
        elif base_path.is_dir():
            if recursive:
                for dirpath, _dirnames, filenames in os.walk(str(base_path)):
                    for fname in filenames:
                        fpath = Path(os.path.join(dirpath, fname))
                        try:
                            if os.path.islink(str(fpath)):
                                continue
                            _accumulate_tags(fpath, tag_map)
                        except (FileTagError, OSError):
                            continue
            else:
                for entry in os.scandir(str(base_path)):
                    if entry.is_file() and not entry.is_symlink():
                        try:
                            _accumulate_tags(Path(entry.path), tag_map)
                        except (FileTagError, OSError):
                            continue
    return tag_map


def _accumulate_tags(fpath: Path, tag_map: dict[str, list[Path]]) -> None:
    """Add a file's tags to the tag map."""
    tags = get_tags(fpath)
    for t in tags:
        if t not in tag_map:
            tag_map[t] = []
        tag_map[t].append(fpath.resolve())


def export_tags(search_paths: list[Path], recursive: bool = True) -> dict[str, list[str]]:
    """
    Export all file-tag mappings as a dictionary.

    Args:
        search_paths: Directories to scan.
        recursive: If True, scan recursively.

    Returns:
        Dictionary mapping file paths (as strings) to lists of tag names.
    """
    result: dict[str, list[str]] = {}
    for base_path in search_paths:
        if not base_path.exists():
            continue
        if base_path.is_file():
            _export_file(base_path, result)
        elif base_path.is_dir():
            if recursive:
                for dirpath, _dirnames, filenames in os.walk(str(base_path)):
                    for fname in filenames:
                        fpath = Path(os.path.join(dirpath, fname))
                        try:
                            if os.path.islink(str(fpath)):
                                continue
                            _export_file(fpath, result)
                        except (FileTagError, OSError):
                            continue
            else:
                for entry in os.scandir(str(base_path)):
                    if entry.is_file() and not entry.is_symlink():
                        try:
                            _export_file(Path(entry.path), result)
                        except (FileTagError, OSError):
                            continue
    return result


def _export_file(fpath: Path, result: dict[str, list[str]]) -> None:
    """Add a file's tags to the export dict."""
    tags = get_tags(fpath)
    if tags:
        result[str(fpath.resolve())] = sorted(tags)


def import_tags(data: dict[str, list[str]]) -> tuple[int, int]:
    """
    Import file-tag mappings from a dictionary.

    Args:
        data: Dictionary mapping file paths (strings) to lists of tag names.

    Returns:
        Tuple of (success_count, error_count).
    """
    success = 0
    errors = 0
    for path_str, tag_list in data.items():
        fpath = Path(path_str)
        try:
            if not fpath.exists():
                errors += 1
                continue
            set_tags(fpath, tag_list)
            success += 1
        except (FileTagError, OSError):
            errors += 1
    return success, errors


def get_stats(search_paths: list[Path], recursive: bool = True) -> dict:
    """
    Get statistics about tagged files.

    Args:
        search_paths: Directories to scan.
        recursive: If True, scan recursively.

    Returns:
        Dictionary with stats: total_files, tagged_files, total_tags, top_tags, etc.
    """
    total_files = 0
    tagged_files = 0
    tag_counts: dict[str, int] = {}

    for base_path in search_paths:
        if not base_path.exists():
            continue
        if base_path.is_file():
            total_files += 1
            _count_tags(base_path, tag_counts, tagged_files)
            if _has_tags(base_path):
                tagged_files += 1
        elif base_path.is_dir():
            if recursive:
                for dirpath, _dirnames, filenames in os.walk(str(base_path)):
                    for fname in filenames:
                        fpath = Path(os.path.join(dirpath, fname))
                        try:
                            if os.path.islink(str(fpath)):
                                continue
                            total_files += 1
                            if _has_tags(fpath):
                                tagged_files += 1
                                _count_tags(fpath, tag_counts, tagged_files)
                        except (FileTagError, OSError):
                            continue
            else:
                for entry in os.scandir(str(base_path)):
                    if entry.is_file() and not entry.is_symlink():
                        try:
                            total_files += 1
                            fpath = Path(entry.path)
                            if _has_tags(fpath):
                                tagged_files += 1
                                _count_tags(fpath, tag_counts, tagged_files)
                        except (FileTagError, OSError):
                            continue

    top_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))[:10]

    return {
        "total_files": total_files,
        "tagged_files": tagged_files,
        "total_tags": len(tag_counts),
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
    }


def _has_tags(fpath: Path) -> bool:
    """Check if a file has any tags."""
    raw = _read_tags_raw(str(fpath))
    return raw is not None and raw.strip() != ""


def _count_tags(fpath: Path, tag_counts: dict[str, int], _tagged_files: int) -> None:
    """Count tags in a file for stats."""
    raw = _read_tags_raw(str(fpath))
    if raw:
        for t in raw.split(TAG_SEPARATOR):
            t = t.strip()
            if t:
                tag_counts[t] = tag_counts.get(t, 0) + 1
