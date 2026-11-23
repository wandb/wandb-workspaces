"""Check the SDK against a real workspace without writing to one.

For each spec it reports what a fetch-then-save without edits would drop,
change or add, for finding regressions in what a save keeps, during the model
migration and after it.

    uv run python -m tests.round_trip_report [SOURCE ...] [--paths N]

SOURCE is a spec file, a directory of them, or a workspace URL. With none, it
reads tests/specs/ and `SPEC_CORPUS`. For each spec it prints how many paths
the save dropped, changed and added, and how many write-contract errors the
saved spec has; `--paths N` also lists up to N paths of each kind.

A URL is fetched read-only with your `wandb login` credentials for its host
(`wandb.ai` reads from api.wandb.ai, `forge.coreweave.com` and
`app.forge.coreweave.com` from api.forge.coreweave.com); set `WANDB_BASE_URL`
to use another API host. The save goes to a fake server and the spec stays in
memory, so nothing is written back or saved to disk: stored workspaces can
hold customer data.
"""

import argparse
import copy
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any, Callable, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

import wandb

from wandb_workspaces._graphql import execute_graphql

from .fake_view_server import fetch_then_save
from .spec_harness import (
    all_specs,
    diff_specs,
    format_path,
    load_spec,
    write_errors,
)

VIEW_QUERY = """
query View($entityName: String, $projectName: String, $viewName: String) {
    project(name: $projectName, entityName: $entityName) {
        allViews(viewType: "project-view", viewName: $viewName) {
            edges { node { id name displayName spec updatedAt } }
        }
    }
}
"""

# A source: its row label, and a function returning (spec, size in KB).
Source = Tuple[str, Callable[[], Tuple[Dict[str, Any], float]]]


def _api_base_url(app_host: str) -> str:
    if os.environ.get("WANDB_BASE_URL"):
        return os.environ["WANDB_BASE_URL"]
    if app_host == "wandb.ai":
        return "https://api.wandb.ai"
    return "https://api." + app_host.removeprefix("app.")


def fetch_view_row(url: str) -> Dict[str, Any]:
    """The stored view row a workspace URL points at, read-only.

    The project is the last two path segments, so a host that prefixes the
    path (Forge's `/wandb/<entity>/<project>`) works. A saved workspace is
    stored as `nw-<id>-v` and a personal one as `nw-<id>-w`; both are tried.
    """
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    nw = parse_qs(parsed.query).get("nw", [None])[0]
    if len(segments) < 2 or not nw:
        raise ValueError(f"{url} is not a workspace URL (/<entity>/<project>?nw=...)")
    entity, project = segments[-2:]

    api = wandb.Api(overrides={"base_url": _api_base_url(parsed.hostname or "")})
    for view_name in (f"nw-{nw}-v", f"nw-{nw}-w", nw):
        response = execute_graphql(
            api,
            VIEW_QUERY,
            {"entityName": entity, "projectName": project, "viewName": view_name},
        )
        if response.get("project") is None:
            raise ValueError(f"project {entity}/{project} not found, or no access")
        edges = response["project"]["allViews"]["edges"]
        if edges:
            return edges[0]["node"]
    raise ValueError(f"no workspace nw={nw} in {entity}/{project}")


def _url_label(url: str) -> str:
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    nw = parse_qs(parsed.query).get("nw", [""])[0]
    return "/".join(segments[-2:] + [nw])


def _url_source(url: str) -> Source:
    def load():
        row = fetch_view_row(url)
        return json.loads(row["spec"]), len(row["spec"]) / 1024

    return _url_label(url), load


def _file_source(path: pathlib.Path) -> Source:
    return path.name, lambda: (load_spec(path), path.stat().st_size / 1024)


def _sources(args: List[str]) -> List[Source]:
    if not args:
        return [_file_source(p) for p in all_specs()]
    sources = []
    for arg in args:
        if arg.startswith(("http://", "https://")):
            sources.append(_url_source(arg))
            continue
        p = pathlib.Path(arg).expanduser()
        files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
        sources += [_file_source(f) for f in files]
    return sources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources", nargs="*", metavar="SOURCE")
    parser.add_argument("--paths", type=int, default=0, metavar="N")
    args = parser.parse_args(argv)

    # The SDK prints a line per save and warns about panel order; keep the
    # report readable.
    wandb.termlog = wandb.termwarn = lambda *a, **k: None
    logging.disable(logging.WARNING)

    sources = _sources(args.sources)
    if not sources:
        sys.exit("No specs found. Pass paths or URLs, or set SPEC_CORPUS.")

    header = (
        f"{'spec':40} {'KB':>8} {'dropped':>8} {'changed':>8} {'added':>8} {'write':>6}"
    )
    print(header)
    print("-" * len(header))
    totals = dict(dropped=0, changed=0, added=0, write=0, failed=0, lossless=0)
    started = time.time()
    for label, load in sources:
        name = label[:40]
        size = 0.0
        try:
            spec, size = load()
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
        f"{len(sources)} specs in {time.time() - started:.1f}s:"
        f" {totals['lossless']} lossless, {totals['failed']} failed to load or save."
        f" Totals: {totals['dropped']} dropped, {totals['changed']} changed,"
        f" {totals['added']} added, {totals['write']} write-contract errors."
    )


if __name__ == "__main__":
    main()
