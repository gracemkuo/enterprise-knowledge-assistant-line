from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare source documents for the search corpus.")
    parser.add_argument("source", type=Path, help="Folder of original files; never modified")
    parser.add_argument("output", type=Path, help="Folder for search-ready files and manifest.json")
    parser.add_argument("--corpus", type=Path,
                        help="JSON file whose documents[].path entries limit the run")
    parser.add_argument("--exclude-column", action="append", default=[], metavar="NAME",
                        help="Workbook column that must not be published; repeatable")
    parser.add_argument("--exclude-rows-marked", action="append", default=[], metavar="TEXT",
                        help="Leave out workbook rows where a cell equals this text; repeatable")
    parser.add_argument("--prune", action="store_true",
                        help="Delete output files that no source file produces any more")
    args = parser.parse_args()
    include = None
    if args.corpus:
        include = [doc["path"] for doc in json.loads(args.corpus.read_text())["documents"]]
    manifest = run(args.source, args.output, include=include, exclude_columns=args.exclude_column,
                   exclude_row_markers=args.exclude_rows_marked, prune=args.prune)
    print(json.dumps(manifest["summary"], ensure_ascii=False))
    for record in manifest["records"]:
        if record["status"] not in ("converted", "passthrough"):
            print(f'{record["status"]}\t{record["path"]}\t{record.get("reason", "")}')
    if manifest["stale_outputs"]:
        print("stale outputs:", ", ".join(manifest["stale_outputs"]))


if __name__ == "__main__":
    main()
