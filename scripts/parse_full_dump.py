"""Stream a Lichess monthly dump (.pgn.zst) into a flat CSV of game metadata.

Grab a file from https://database.lichess.org (~30 GB compressed per month,
~100M games), then:

    python parse_full_dump.py lichess_db_standard_rated_2026-06.pgn.zst games_big.csv --limit 500000 --every 200

Memory use is constant regardless of file size: the zstd stream is decoded on
the fly and only headers are parsed (roughly 10x faster than full game parsing;
move counts require full parsing, which this deliberately skips).
 
Sampling note, stated precisely because the obvious reading is wrong. The dump
is ordered by end time, so the first N games are a time-of-day/weekday-biased
slice. --every k thins that slice but does not escape it: the script stops once
--limit games have been written, so it reads only the first (limit * k) eligible
games and never sees the rest of the month.
 
Choose k against the dump's total game count, not arbitrarily. A month holds
roughly 100M games, so --limit 500000 --every 200 spans the full month, while
--every 50 covers only its first quarter, about the first week, with the
weekday skew still intact. The script cannot pick k for you: the total is
unknown without a counting pass over the whole file, which would double the
runtime.

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

def is_rated(headers) -> bool:
    """Lichess writes Event as e.g. 'Rated Blitz game' or 'Casual Bullet game'.
 
    Tournament games follow the same convention ('Rated Blitz tournament ...'),
    so the leading word is the reliable signal.
    The standard_rated dumps are all rated, but pointing this at a full
    `standard` dump would otherwise silently label every casual game as rated.
    """
    return headers.get("Event", "").strip().lower().startswith("rated")

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
                "TRUE" if is_rated(headers) else "FALSE",
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
