"""Entry point / I-O and orchestration only. No address algorithms here.

Local CLI protocol is provisional until the instructor confirms the judge API.
Run: python -m src.main --input examples/addresses.txt --database-dir data
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from typing import Iterable, Iterator, Mapping, TextIO

OUTPUT_FIELDS = ("street", "ward", "province")


class ModuleNotReadyError(RuntimeError):
    """A teammate-owned module has not been implemented yet."""


def read_addresses(stream: TextIO) -> Iterator[str]:
    """One raw address per line; remove only the line terminator."""
    for line in stream:
        if line.endswith("\n"):
            line = line[:-1]
            if line.endswith("\r"):
                line = line[:-1]
        yield line


def validate_output(result: Mapping[str, object]) -> dict[str, str | None]:
    """Reject incompatible search results instead of silently changing them."""
    if not isinstance(result, Mapping) or set(result) != set(OUTPUT_FIELDS):
        raise ValueError(f"Search result must contain exactly: {OUTPUT_FIELDS}")
    for field in OUTPUT_FIELDS:
        value = result[field]
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{field} must be a string or None; got {type(value).__name__}")
    return {key: result[key] for key in OUTPUT_FIELDS}  # type: ignore[misc]


def write_result(stream: TextIO, result: Mapping[str, object]) -> None:
    """Write one UTF-8 JSON object on one line (developer adapter only)."""
    stream.write(json.dumps(validate_output(result), ensure_ascii=False) + "\n")


def _load_teammate_functions():
    """Import at execution time, so --help and I/O tests work before implementation."""
    try:
        from src.database.builder import build_index
        from src.address_segmentation.segmenter import segment_address
        from src.searching.searcher import search_address
    except ModuleNotFoundError as exc:
        expected = {
            "src.database.builder", "src.address_segmentation.segmenter",
            "src.searching.searcher",
        }
        if exc.name in expected:
            raise ModuleNotReadyError(
                "Teammate modules are still empty. Implement the functions "
                "specified in contract.md before running the full pipeline. "
                f"Missing: {exc.name}"
            ) from exc
        raise
    return build_index, segment_address, search_address


def run_pipeline(
    addresses: Iterable[str], database_dir: Path, output_stream: TextIO
) -> None:
    """Index once; then segment, search and write each request."""
    build_index, segment_address, search_address = _load_teammate_functions()
    index = build_index(database_dir)
    for raw_address in addresses:
        segmented = segment_address(raw_address)
        if not isinstance(segmented, dict):
            raise TypeError("segment_address must return a dict (see contract.md)")
        if segmented.get("raw_address") != raw_address:
            raise ValueError("segment_address must preserve raw_address")
        result = search_address(segmented, index)
        write_result(output_stream, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Address segmentation (team skeleton)")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--address", help="One raw address for local testing")
    source.add_argument("--input", type=Path, help="UTF-8 text file, one address per line")
    parser.add_argument("--database-dir", type=Path, default=Path("data"),
                        help="Directory containing instructor-provided reference files")
    parser.add_argument("--output", type=Path, help="Output JSONL file (default: stdout)")
    args = parser.parse_args(argv)

    try:
        with ExitStack() as stack:
            if args.address is not None:
                addresses: Iterable[str] = (args.address,)
            elif args.input is not None:
                input_stream = stack.enter_context(args.input.open("r", encoding="utf-8-sig", newline=""))
                addresses = read_addresses(input_stream)
            else:
                addresses = read_addresses(sys.stdin)

            out: TextIO = (
                stack.enter_context(args.output.open("w", encoding="utf-8", newline="\n"))
                if args.output else sys.stdout
            )
            run_pipeline(addresses, args.database_dir, out)
    except (OSError, ValueError, TypeError, ModuleNotReadyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
