import pytest

import wandb_workspaces.reports.v1 as wr_v1
import wandb_workspaces.reports.v2 as wr


class _ServiceApi:
    app_url = "https://service.wandb.test/"


class _Api:
    default_entity = "ent"

    def __init__(self):
        self._service_api = _ServiceApi()


@pytest.mark.parametrize(
    "title,slug",
    [
        (
            "RL Experiment Decision Report — JetBlue Prime",
            "RL-Experiment-Decision-Report-JetBlue-Prime",
        ),
        ("25%engag_emb+flat", "25-engag_emb-flat"),
        # re's \W is Unicode-aware, so a CJK title used to survive into the slug
        # and get percent-encoded.
        ("数据集 0", "-0"),
        ("Report: v1.2 (final)", "Report-v1-2-final-"),
    ],
)
def test_report_url_slug_has_no_percent_escapes(monkeypatch, title, slug):
    monkeypatch.setattr(wr.interface, "_get_api", lambda: _Api())

    v2 = wr.Report(project="proj", entity="ent", title=title)
    v2.id = "abc123"
    v1 = wr_v1.Report(project="proj", entity="ent", title=title, _api=_Api())
    v1._viewspec["id"] = "abc123=="

    expected = f"https://service.wandb.test/ent/proj/reports/{slug}--abc123"
    assert v2.url == expected
    assert v1.url == expected
    assert "%" not in v2.url
