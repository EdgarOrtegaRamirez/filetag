# FileTag

**Tag, search, and organize files using filesystem extended attributes.**

[![CI](https://github.com/EdgarOrtegaRamirez/filetag/actions/workflows/ci.yml/badge.svg)](https://github.com/EdgarOrtegaRamirez/filetag/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/filetag.svg)](https://pypi.org/project/filetag/)

FileTag is a command-line tool that lets you **tag files with metadata** using filesystem extended attributes (xattr). Tags are stored directly on the filesystem — no database, no sidecar files, no lock-in. Works on Linux (ext4, xfs, btrfs, ZFS) and macOS (APFS, HFS+).

## Why FileTag?

- **Organize without moving** — Tag files where they are, don't reorganize your directory structure
- **No lock-in** — Tags are stored as standard xattr; any tool can read them
- **Fast** — No database queries, no indexing; xattr is a native filesystem operation
- **Cross-platform** — Linux and macOS (Windows support via ADS is planned)
- **Scriptable** — JSON output for integration with other tools

## Installation

```bash
# Install from PyPI
pip install filetag

# Install from source
git clone https://github.com/EdgarOrtegaRamirez/filetag.git
cd filetag
pip install -e .
```

## Quick Start

```bash
# Tag some files
filetag add report.pdf -t important -t work
filetag add notes.txt -t personal -t reference

# List tags on a file
filetag list report.pdf
# Output: report.pdf: important, work

# Find files by tag
filetag find important
# Output: Found 1 file(s):
#   /home/user/report.pdf  [important, work]

# Show all tags in a directory
filetag show --path ~/documents

# Tag statistics
filetag stats
```

## Commands

| Command | Description |
|---------|-------------|
| `add` | Add tags to files |
| `remove` | Remove tags from files |
| `list` | List tags on files or show tag summary for directories |
| `clear` | Remove all tags from files |
| `find` | Find files by tag (supports `--all` and `--any` matching) |
| `show` | Show all tags and their associated files |
| `stats` | Show tagging statistics |
| `export` | Export file-tag mappings as JSON |
| `import` | Import file-tag mappings from JSON |

## Usage Examples

### Tag management

```bash
# Add tags
filetag add report.pdf -t important -t work -t confidential

# Add multiple tags at once
filetag add *.py -t python -t script

# Remove tags
filetag remove report.pdf -t confidential

# Remove all tags from a file
filetag clear report.pdf

# Replace all tags on a file
filetag add paper.pdf -t draft
filetag add paper.pdf -t final  # Adds "final" alongside "draft"
filetag clear paper.pdf
filetag add paper.pdf -t final  # Now only "final"
```

### Finding files

```bash
# Find files with any of these tags
filetag find important urgent

# Find files with ALL of these tags
filetag find python web --all

# Search in specific directories
filetag find work --path ~/documents --path ~/projects

# Non-recursive search
filetag find important --no-recursive

# JSON output for scripting
filetag find important --json
```

### Export/Import

```bash
# Export all tags to JSON
filetag export --output tags-backup.json

# Import tags from JSON
filetag import tags-backup.json
```

### Statistics

```bash
filetag stats --path ~/projects
# Output:
# FileTag Statistics:
#   Total files scanned:  1542
#   Tagged files:         89
#   Unique tags:          12
#
#   Top tags:
#     python: 45 file(s)
#     important: 23 file(s)
#     work: 18 file(s)
```

## Tag Format

- Tags are stored in the `user.filetag.tags` extended attribute
- Tags are comma-separated: `important,work,urgent`
- Tags are case-insensitive (stored as lowercase)
- Valid characters: letters, numbers, hyphens (`-`), underscores (`_`), dots (`.`)
- Maximum tag length: 64 characters

## Filesystem Requirements

Extended attributes must be supported on your filesystem:

| OS | Filesystem | Support |
|----|------------|---------|
| Linux | ext4 | ✅ Enabled by default |
| Linux | xfs | ✅ Enabled by default |
| Linux | btrfs | ✅ Enabled by default |
| Linux | ZFS | ✅ |
| macOS | APFS | ✅ |
| macOS | HFS+ | ✅ |

To verify xattr support on a filesystem:

```bash
touch /tmp/test-xattr && xattr -w user.test value /tmp/test-xattr
```

## Development

```bash
# Clone the repository
git clone https://github.com/EdgarOrtegaRamirez/filetag.git
cd filetag

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=filetag
```

## Project Structure

```
filetag/
├── src/
│   └── filetag/
│       ├── __init__.py    # Package metadata
│       ├── cli.py         # Click CLI interface
│       └── core.py        # Core tagging logic
├── tests/
│   └── test_core.py       # Tests (mock xattr backend)
├── pyproject.toml          # Project configuration
├── AGENTS.md               # AI agent documentation
├── SECURITY.md             # Security notes
└── README.md
```

## License

MIT

## Security

See [SECURITY.md](SECURITY.md) for security considerations and reporting.