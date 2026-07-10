# FileTag — AI Agent Documentation

## Overview

FileTag is a Python CLI tool for tagging files using filesystem extended attributes (xattr). It provides commands for adding, removing, listing, finding, and exporting tags on files.

## Architecture

```
src/filetag/
├── __init__.py   # Package metadata, version
├── cli.py        # Click CLI entry point with subcommands
└── core.py       # Core tagging logic using xattr
```

### Key Design Decisions

1. **Tags stored in a single xattr key** (`user.filetag.tags`) as comma-separated values
2. **Mockable xattr backend** — tests use `unittest.mock.patch` to mock the `xattr` module
3. **Tag validation** — tags are lowercased, trimmed, and validated against `^[a-zA-Z0-9_.-]+$`
4. **Cross-platform** — Linux and macOS via the `xattr` Python library

## Commands

| Command | Function | Description |
|---------|----------|-------------|
| `add` | `add_tags()` | Add tags to files |
| `remove` | `remove_tags()` | Remove tags from files |
| `list` | `get_tags()` / `list_all_tags()` | List tags on files or directories |
| `clear` | `clear_tags()` | Remove all tags |
| `find` | `find_by_tag()` | Find files by tag(s) |
| `show` | `list_all_tags()` | Show all tags and their files |
| `stats` | `get_stats()` | Tagging statistics |
| `export` | `export_tags()` | Export to JSON |
| `import` | `import_tags()` | Import from JSON |

## Key APIs

### `core.py`

- `get_tags(path) -> Set[str]` — Get tags for a file
- `add_tags(path, tags) -> Set[str]` — Add tags to a file
- `remove_tags(path, tags) -> Set[str]` — Remove tags from a file
- `clear_tags(path)` — Remove all tags from a file
- `set_tags(path, tags) -> Set[str]` — Replace all tags
- `find_by_tag(paths, tags, match_all, recursive) -> List[Tuple[Path, Set[str]]]` — Find files by tag
- `list_all_tags(paths, recursive) -> Dict[str, List[Path]]` — List all tags
- `export_tags(paths, recursive) -> Dict[str, List[str]]` — Export as JSON-compatible dict
- `import_tags(data) -> Tuple[int, int]` — Import from dict
- `get_stats(paths, recursive) -> Dict` — Get statistics
- `validate_tag(tag) -> str` — Validate and normalize a tag name

## Testing

Tests use a mock xattr backend (`MockXAttr`) to avoid requiring actual xattr filesystem support. Tests cover:

- Core tag operations (add, remove, list, clear, set)
- Tag validation (valid, invalid, empty, too long)
- Find operations (single, any, all, recursive, no match)
- Export/import round-trips
- Statistics
- CLI integration tests via Click's CliRunner
- Error handling (file not found, invalid tags, xattr unsupported, xattr unavailable)

Run tests: `pytest`

## Dependencies

- `click>=8.1.0,<9.0.0` — CLI framework
- `xattr>=1.0.0,<2.0.0` — Extended attributes interface

## Filesystem Support

Requires xattr-capable filesystem: ext4, xfs, btrfs, ZFS (Linux), APFS, HFS+ (macOS).