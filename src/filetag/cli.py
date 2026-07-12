"""
CLI module for FileTag - Command-line interface using Click.

Provides commands for:
- add: Add tags to files
- remove: Remove tags from files
- list: List tags on files
- clear: Clear all tags from files
- find: Find files by tag
- show: Show all tags and their files
- stats: Show tagging statistics
- export: Export tags to JSON
- import_: Import tags from JSON
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from filetag import __version__
from filetag.core import (
    add_tags,
    clear_tags,
    export_tags,
    find_by_tag,
    get_stats,
    get_tags,
    import_tags,
    list_all_tags,
    remove_tags,
)


def _print_tags(tags, prefix=""):
    """Format and print a set of tags."""
    if not tags:
        click.echo(f"{prefix}(no tags)")
    else:
        click.echo(f"{prefix}{', '.join(sorted(tags))}")


def _resolve_paths(paths: list[str]) -> list[Path]:
    """Resolve path strings to Path objects, expanding ~."""
    result = []
    for p in paths:
        expanded = os.path.expanduser(p)
        resolved = Path(expanded).resolve()
        result.append(resolved)
    return result


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="filetag")
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable debug output.",
)
def main(debug: bool) -> None:
    """FileTag - Tag and organize files using extended attributes.

    FileTag stores tags as extended attributes (xattr) on files, allowing
    you to organize and find files without moving them or changing their names.

    Tags are stored in the 'user.filetag.tags' xattr as a comma-separated list.
    Requires a filesystem that supports extended attributes (ext4, xfs, btrfs,
    ZFS, APFS, etc.).

    \b
    Quick start:
        filetag add report.pdf important work
        filetag list report.pdf
        filetag find important
        filetag stats
    """
    if debug:
        import logging

        logging.basicConfig(level=logging.DEBUG)


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--tag",
    "-t",
    "tags",
    multiple=True,
    required=True,
    help="Tag to add (can be specified multiple times).",
)
def add(paths, tags):
    """Add tags to files.

    PATHS: One or more file/directory paths.

    \b
    Examples:
        filetag add doc.pdf -t important -t work
        filetag add *.py -t python -t script
    """
    resolved = _resolve_paths(list(paths))
    for path in resolved:
        try:
            result = add_tags(path, list(tags))
            click.echo(f"  {path}: ", nl=False)
            _print_tags(result)
        except Exception as e:
            click.echo(f"  Error: {path}: {e}", err=True)


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--tag",
    "-t",
    "tags",
    multiple=True,
    required=True,
    help="Tag to remove (can be specified multiple times).",
)
def remove(paths, tags):
    """Remove tags from files.

    PATHS: One or more file/directory paths.

    \b
    Examples:
        filetag remove doc.pdf -t temp
        filetag remove *.py -t deprecated -t old
    """
    resolved = _resolve_paths(list(paths))
    for path in resolved:
        try:
            result = remove_tags(path, list(tags))
            click.echo(f"  {path}: ", nl=False)
            _print_tags(result)
        except Exception as e:
            click.echo(f"  Error: {path}: {e}", err=True)


@main.command()
@click.argument("paths", nargs=-1, required=False, type=click.Path(exists=True))
def list_cmd(paths):
    """List tags on files.

    PATHS: One or more file/directory paths. If omitted, uses current directory.

    \b
    Examples:
        filetag list
        filetag list doc.pdf src/
    """
    if not paths:
        paths = ["."]
    resolved = _resolve_paths(list(paths))
    for path in resolved:
        if path.is_dir():
            click.echo(f"\n{path}/:")
            all_tags = list_all_tags([path], recursive=True)
            if all_tags:
                for tag, files in sorted(all_tags.items()):
                    click.echo(f"    {tag}: {len(files)} file(s)")
            else:
                click.echo("    (no tagged files found)")
        else:
            try:
                tags = get_tags(path)
                click.echo(f"  {path}: ", nl=False)
                _print_tags(tags)
            except Exception as e:
                click.echo(f"  Error: {path}: {e}", err=True)


@main.command()
@click.argument("paths", nargs=-1, required=False, type=click.Path(exists=True))
def clear(paths):
    """Remove all tags from files.

    PATHS: One or more file paths. If omitted, clears nothing (use --all).

    \b
    Examples:
        filetag clear doc.pdf
    """
    if not paths:
        click.echo("No paths specified. Use 'filetag clear <paths>' to clear tags.")
        return
    resolved = _resolve_paths(list(paths))
    for path in resolved:
        try:
            old_tags = get_tags(path)
            clear_tags(path)
            click.echo(f"  Cleared {path}: ", nl=False)
            _print_tags(old_tags, prefix="removed ")
        except Exception as e:
            click.echo(f"  Error: {path}: {e}", err=True)


@main.command()
@click.argument("tags", nargs=-1, required=True)
@click.option(
    "--path",
    "-p",
    "search_paths",
    multiple=True,
    default=["."],
    help="Directory to search (can be specified multiple times).",
    type=click.Path(exists=True),
)
@click.option(
    "--all/--any",
    "match_all",
    default=False,
    help="--all: files must have ALL specified tags. --any: any tag match.",
)
@click.option(
    "--no-recursive",
    is_flag=True,
    default=False,
    help="Only search the given directory, not subdirectories.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output results as JSON.",
)
def find(tags, search_paths, match_all, no_recursive, json_output):
    """Find files by tag.

    TAGS: One or more tag names to search for.

    \b
    Examples:
        filetag find important
        filetag find python script --all
        filetag find work --path ~/documents
    """
    resolved = _resolve_paths(list(search_paths))
    try:
        results = find_by_tag(
            resolved,
            list(tags),
            match_all=match_all,
            recursive=not no_recursive,
        )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_output:
        data = {str(path): sorted(t) for path, t in results}
        click.echo(json.dumps(data, indent=2))
    else:
        if not results:
            click.echo("No matching files found.")
            return
        click.echo(f"Found {len(results)} file(s):\n")
        for path, file_tags in sorted(results):
            click.echo(f"  {path}", nl=False)
            if file_tags:
                click.echo(f"  [{', '.join(sorted(file_tags))}]")
            else:
                click.echo()


@main.command()
@click.option(
    "--path",
    "-p",
    "search_paths",
    multiple=True,
    default=["."],
    help="Directory to scan (can be specified multiple times).",
    type=click.Path(exists=True),
)
@click.option(
    "--no-recursive",
    is_flag=True,
    default=False,
    help="Only scan the given directory, not subdirectories.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output results as JSON.",
)
def show(search_paths, no_recursive, json_output):
    """Show all tags and their associated files.

    \b
    Examples:
        filetag show
        filetag show --path ~/documents --json
    """
    resolved = _resolve_paths(list(search_paths))
    try:
        tag_map = list_all_tags(resolved, recursive=not no_recursive)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_output:
        data = {tag: [str(p) for p in paths] for tag, paths in tag_map.items()}
        click.echo(json.dumps(data, indent=2))
    else:
        if not tag_map:
            click.echo("No tags found.")
            return
        click.echo(f"Found {len(tag_map)} unique tag(s):\n")
        for tag, files in sorted(tag_map.items()):
            click.echo(f"  {tag} ({len(files)} file(s))")
            for f in sorted(files):
                click.echo(f"    - {f}")


@main.command()
@click.option(
    "--path",
    "-p",
    "search_paths",
    multiple=True,
    default=["."],
    help="Directory to scan (can be specified multiple times).",
    type=click.Path(exists=True),
)
@click.option(
    "--no-recursive",
    is_flag=True,
    default=False,
    help="Only scan the given directory, not subdirectories.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output results as JSON.",
)
def stats(search_paths, no_recursive, json_output):
    """Show tagging statistics.

    \b
    Examples:
        filetag stats
        filetag stats --path ~/projects
    """
    resolved = _resolve_paths(list(search_paths))
    try:
        data = get_stats(resolved, recursive=not no_recursive)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_output:
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo("FileTag Statistics:")
        click.echo(f"  Total files scanned:  {data['total_files']}")
        click.echo(f"  Tagged files:         {data['tagged_files']}")
        click.echo(f"  Unique tags:          {data['total_tags']}")
        if data["top_tags"]:
            click.echo("\n  Top tags:")
            for tag_info in data["top_tags"]:
                click.echo(f"    {tag_info['tag']}: {tag_info['count']} file(s)")


@main.command()
@click.option(
    "--path",
    "-p",
    "search_paths",
    multiple=True,
    default=["."],
    help="Directory to scan (can be specified multiple times).",
    type=click.Path(exists=True),
)
@click.option(
    "--no-recursive",
    is_flag=True,
    default=False,
    help="Only scan the given directory, not subdirectories.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    help="Write JSON output to file instead of stdout.",
    type=click.Path(writable=True),
)
def export(search_paths, no_recursive, output_file):
    """Export file-tag mappings as JSON.

    \b
    Example:
        filetag export --output tags.json
        filetag export --path ~/documents
    """
    resolved = _resolve_paths(list(search_paths))
    try:
        data = export_tags(resolved, recursive=not no_recursive)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    json_str = json.dumps(data, indent=2)
    if output_file:
        Path(output_file).write_text(json_str)
        click.echo(f"Exported {len(data)} file(s) to {output_file}")
    else:
        click.echo(json_str)


@main.command(name="import")
@click.argument("input_file", type=click.Path(exists=True, readable=True))
def import_cmd(input_file):
    """Import file-tag mappings from a JSON file.

    \b
    Example:
        filetag import tags.json
    """
    try:
        data = json.loads(Path(input_file).read_text())
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in {input_file}: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to read {input_file}: {e}", err=True)
        sys.exit(1)

    if not isinstance(data, dict):
        click.echo("Error: Expected a JSON object (file -> tags mapping).", err=True)
        sys.exit(1)

    try:
        success, errors = import_tags(data)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Imported tags: {success} file(s) updated, {errors} error(s)")


if __name__ == "__main__":
    main()
