import subprocess
import sys
import textwrap
import types

from wandb_workspaces._graphql import execute_graphql


def test_report_and_workspace_imports_do_not_require_wandb_gql():
    script = textwrap.dedent(
        """
        import builtins
        import importlib
        import sys

        import wandb

        for module_name in list(sys.modules):
            if module_name == "wandb_gql" or module_name.startswith("wandb_gql."):
                del sys.modules[module_name]

        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == "wandb_gql" or name.startswith("wandb_gql."):
                raise ModuleNotFoundError("No module named 'wandb_gql'")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = guarded_import

        for module_name in [
            "wandb_workspaces.reports.v1.mutations",
            "wandb_workspaces.reports.v2",
            "wandb_workspaces.workspaces.internal",
        ]:
            importlib.import_module(module_name)

        print("ok")
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_execute_graphql_prefers_service_api():
    class ServiceApi:
        def __init__(self):
            self.calls = []

        def execute_graphql(self, query, variables=None):
            self.calls.append((query, variables))
            return {"ok": True}

    class Api:
        def __init__(self):
            self._service_api = ServiceApi()

    api = Api()
    result = execute_graphql(api, "query Test { viewer { id } }", {"x": 1})

    assert result == {"ok": True}
    assert api._service_api.calls == [("query Test { viewer { id } }", {"x": 1})]


def test_execute_graphql_lazily_uses_wandb_gql_for_legacy_clients(monkeypatch):
    class Client:
        def __init__(self):
            self.calls = []

        def execute(self, query, *, variable_values):
            self.calls.append((query, variable_values))
            return {"ok": True}

    class Api:
        def __init__(self):
            self.client = Client()

    fake_wandb_gql = types.SimpleNamespace(gql=lambda query: f"parsed:{query}")
    monkeypatch.setitem(sys.modules, "wandb_gql", fake_wandb_gql)

    api = Api()
    result = execute_graphql(api, "query Test { viewer { id } }", {"x": 1})

    assert result == {"ok": True}
    assert api.client.calls == [("parsed:query Test { viewer { id } }", {"x": 1})]
