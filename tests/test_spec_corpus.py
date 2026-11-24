"""Fetch-then-save every spec in the corpus and check nothing is lost.

The committed specs in tests/specs/ stand for workspaces the app authored
today: each must itself pass the write contract, so a fixture cannot carry a
key the app would not save. app-panel-sandbox.json is a workspace the app
saved on Forge, with the root `vizExpanded` and `libraryExpanded` removed:
the app still writes them, but the schema calls them stray. Each spec is
loaded, saved without edits, and checked three ways: the save drops or
changes nothing, adds nothing, and passes the write contract.

Specs under `SPEC_CORPUS` (outside the repo) are marked `corpus` and only
checked for loss: stored workspaces still carry legacy keys that load
migrates, so they fail the write contract until gorilla's transformations
strip them (WB-42793). Run them with:

    SPEC_CORPUS=~/specs uv run pytest tests/test_spec_corpus.py -m corpus

For counts across a corpus, use `python -m tests.round_trip_report`.
"""

import copy

import pytest

from .fake_view_server import fetch_then_save
from .spec_harness import (
    committed_specs,
    corpus_root,
    corpus_specs,
    diff_specs,
    load_spec,
    write_errors,
)

# Committed specs that fail a check on main, by file stem, one set per check.
# Strict, so a spec that starts passing a check must come off that set. Only
# an AssertionError counts, so a crash while loading or saving still shows.
LOSES_FIELDS_ON_MAIN = {"app-panel-sandbox", "unmodeled-fields"}
ADDS_FIELDS_ON_MAIN = {"app-panel-sandbox", "unmodeled-fields"}
BREAKS_WRITE_CONTRACT_ON_MAIN = {"app-panel-sandbox", "unmodeled-fields"}


def _committed(failing_on_main=frozenset(), reason=""):
    mark = pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)
    return [
        pytest.param(
            p,
            id=p.stem,
            marks=[mark] if p.stem in failing_on_main else [],
        )
        for p in committed_specs()
    ]


def _corpus():
    root = corpus_root()
    return [
        pytest.param(p, id=f"corpus/{p.relative_to(root)}", marks=[pytest.mark.corpus])
        for p in corpus_specs()
    ]


def _saved(path):
    spec = load_spec(path)
    return spec, fetch_then_save(copy.deepcopy(spec))


def _format_errors(errors):
    return "\n".join(f"{path}: {message}" for path, message in errors)


@pytest.mark.parametrize("path", _committed())
def test_committed_spec_is_one_the_app_would_save(path):
    errors = write_errors(load_spec(path))
    assert not errors, _format_errors(errors)


@pytest.mark.parametrize(
    "path",
    _committed(LOSES_FIELDS_ON_MAIN, reason="main drops or rewrites fields on save")
    + _corpus(),
)
def test_unedited_save_loses_nothing(path):
    spec, saved = _saved(path)
    diff = diff_specs(spec, saved)
    assert diff.is_lossless, diff.summary()


@pytest.mark.parametrize(
    "path",
    _committed(ADDS_FIELDS_ON_MAIN, reason="main adds default keys on save"),
)
def test_unedited_save_adds_nothing(path):
    spec, saved = _saved(path)
    diff = diff_specs(spec, saved)
    assert not diff.added, diff.summary()


@pytest.mark.parametrize(
    "path",
    _committed(
        BREAKS_WRITE_CONTRACT_ON_MAIN,
        reason=(
            "main writes keys the write contract rejects, such as the root"
            " vizExpanded and libraryExpanded"
        ),
    ),
)
def test_unedited_save_passes_the_write_contract(path):
    _, saved = _saved(path)
    errors = write_errors(saved)
    assert not errors, _format_errors(errors)
