"""
Generate the sample corpus of research-paper PDFs.

The corpus itself lives in :mod:`rpra.sample_corpus` so that a deployed server
can seed itself without needing this scripts directory. This is the command-line
front end.

Usage
-----
    python scripts/make_sample_corpus.py [output_dir]

Defaults to ./data/papers.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpra.sample_corpus import PAPERS, build_corpus


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./data/papers")
    written = build_corpus(out_dir)

    print(f"Wrote {len(written)} PDFs to {out_dir.resolve()}")
    for path in written:
        print(f"  - {path.name}")
    print()
    print(f"Planted findings: {len(PAPERS)} papers, 2 contradiction pairs")
    print("Next: rpra run --extraction-backend heuristic --no-nli")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
