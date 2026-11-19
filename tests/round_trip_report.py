"""Report what a no-edit fetch-then-save does to each spec in a corpus.

    uv run python -m tests.round_trip_report [PATH ...] [--paths N]

PATH is a spec file or a directory of them. With none, it reads
tests/specs/ and `SPEC_CORPUS`. For each spec it prints how many paths the
save dropped, changed and added, and how many write-contract errors the saved
spec has; `--paths N` also lists up to N paths of each kind.
"""

import argparse
import copy
import logging
import pathlib
import sys
import time

import wandb

from .fake_view_server import fetch_then_save
from .spec_harness import all_specs, diff_specs, format_path, load_spec, write_errors


def _spec_files(args):
    if not args:
        return list(all_specs())
    files = []
    for arg in args:
        p = pathlib.Path(arg).expanduser()
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("specs", nargs="*")
    parser.add_argument("--paths", type=int, default=0, metavar="N")
    args = parser.parse_args(argv)

    # The SDK prints a line per save and warns about panel order; keep the
    # report readable.
    wandb.termlog = wandb.termwarn = lambda *a, **k: None
    logging.disable(logging.WARNING)

    files = _spec_files(args.specs)
    if not files:
        sys.exit("No specs found. Pass paths, or set SPEC_CORPUS.")

    header = (
        f"{'spec':40} {'KB':>8} {'dropped':>8} {'changed':>8} {'added':>8} {'write':>6}"
    )
    print(header)
    print("-" * len(header))
    totals = dict(dropped=0, changed=0, added=0, write=0, failed=0, lossless=0)
    started = time.time()
    for path in files:
        name = path.name[:40]
        size = path.stat().st_size / 1024
        try:
            spec = load_spec(path)
            saved = fetch_then_save(copy.deepcopy(spec))
        except Exception as e:
            totals["failed"] += 1
            first_line = (str(e).splitlines() or [""])[0]
            print(
                f"{name:40} {size:8.0f}  failed: {type(e).__name__}: {first_line}"[:200]
            )
            continue
        diff = diff_specs(spec, saved)
        n_write = len(write_errors(saved))
        totals["dropped"] += len(diff.dropped)
        totals["changed"] += len(diff.changed)
        totals["added"] += len(diff.added)
        totals["write"] += n_write
        totals["lossless"] += diff.is_lossless
        print(
            f"{name:40} {size:8.0f} {len(diff.dropped):8} {len(diff.changed):8}"
            f" {len(diff.added):8} {n_write:6}"
        )
        if args.paths:
            for kind in ("dropped", "changed", "added"):
                for p in getattr(diff, kind)[: args.paths]:
                    print(f"    {kind:8} {format_path(p)}")

    print("-" * len(header))
    print(
        f"{len(files)} specs in {time.time() - started:.1f}s:"
        f" {totals['lossless']} lossless, {totals['failed']} failed to load or save."
        f" Totals: {totals['dropped']} dropped, {totals['changed']} changed,"
        f" {totals['added']} added, {totals['write']} write-contract errors."
    )


if __name__ == "__main__":
    main()
