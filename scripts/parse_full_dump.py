"""Stream a Lichess monthly dump (.pgn.zst) into a flat CSV of game metadata.

Grab a file from https://database.lichess.org (~30 GB compressed per month,
~100M games), then:

    python parse_full_dump.py lichess_db_standard_rated_2026-06.pgn.zst games_big.csv --limit 500000 --every 50

Memory use is constant regardless of file size: the zstd stream is decoded on
the fly and only headers are parsed (roughly 10x faster than full game parsing;
move counts require full parsing, which this deliberately skips).

Sampling note: the dump is ordered by end time, so taking the first N games is
a time-of-day/weekday-biased slice. Use --every k to take every k-th game
instead, and set --limit to cap the output size.

Schema differences vs the 20k API scrape used in the notebook:
  - TimeControl is "base_seconds+inc" (seconds, not minutes)
  - Termination values ("Normal", "Time forfeit", ...) differ from the
    notebook's victory_status labels
"""

import argparse
import csv
import io
import sys

import chess.pgn
import zstandard

COLS = [
    "rated", "victory_status", "winner", "time_control",
    "white_rating", "black_rating", "opening_eco", "opening_name",
]

RESULT_MAP = {"1-0": "white", "0-1": "black", "1/2-1/2": "draw"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="path to lichess_db_*.pgn.zst")
    ap.add_argument("out", help="output CSV path")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after writing this many games (default: all)")
    ap.add_argument("--every", type=int, default=1,
                    help="keep every k-th eligible game (default 1 = keep all)")
    args = ap.parse_args()

    seen = kept = 0
    with open(args.src, "rb") as fh, open(args.out, "w", newline="") as out:
        reader = io.TextIOWrapper(
            zstandard.ZstdDecompressor(max_window_size=2 ** 31).stream_reader(fh),
            encoding="utf-8",
        )
        writer = csv.writer(out)
        writer.writerow(COLS)

        while True:
            headers = chess.pgn.read_headers(reader)
            if headers is None:
                break
            if headers.get("WhiteElo", "?") == "?" or headers.get("BlackElo", "?") == "?":
                continue
            winner = RESULT_MAP.get(headers.get("Result", "*"))
            if winner is None:
                continue  # unfinished/aborted
            seen += 1
            if seen % args.every:
                continue
            writer.writerow([
                "TRUE",
                headers.get("Termination", "").lower(),
                winner,
                headers.get("TimeControl", ""),
                headers.get("WhiteElo"),
                headers.get("BlackElo"),
                headers.get("ECO", ""),
                headers.get("Opening", ""),
            ])
            kept += 1
            if kept % 100_000 == 0:
                print(f"{kept:,} games written...", file=sys.stderr)
            if args.limit and kept >= args.limit:
                break

    print(f"done: {kept:,} games written to {args.out}")


if __name__ == "__main__":
    main()
