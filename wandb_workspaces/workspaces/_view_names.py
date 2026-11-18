"""How workspace view names map to the `nw` URL query parameter."""

from wandb.sdk.lib import runid


def _internal_name_to_url_query_str(name: str) -> str:
    name = name.replace("nw-", "").replace("-v", "")
    return name


def _url_query_str_to_internal_name(name: str) -> str:
    return f"nw-{name}-v"


def _generate_view_name() -> str:
    random_id = runid.generate_id(11)
    name = _url_query_str_to_internal_name(random_id)
    return name
