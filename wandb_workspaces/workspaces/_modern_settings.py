"""Translate between the legacy `settings` block and the app's current shape.

A workspace's line plot settings used to live in `section.settings` and a
section's in `localPanelSettings`, both as the schema's `Settings`. The app
now keeps them as `OrganizedSettings` in `section.workspaceSettings` and a
section's `sectionSettings`, with the line plot settings under `linePlot`.
On load it migrates the legacy blocks, but only when the modern block is
empty, so a spec that has both is read from the modern one alone.

The SDK's internal models still use the legacy shape. `organized_from_legacy`
is the app's migration (`getMigratedSettings` in wandb/core,
frontends/app/src/components/WorkspaceDrawer/Settings/migrateSettings.ts),
applied when the SDK writes, so what it saves is what the app would have made
of the legacy block. `legacy_from_organized` is its inverse, for reading a
modern spec into the internal models.

A save of a loaded workspace must write the whole modern block or none of
it: the app ignores the legacy block as soon as the modern one has a key.
`seed_modern_blocks` gives the loaded spec the block the app would migrate
to, so the save's edits land on top of it, and `unseed_untouched` takes the
seed back out wherever no edit reached it, so an unedited save sends the
spec as loaded.
"""

from typing import Any, Dict, List, Tuple

# The keys of the app's `LinePlotSettings` type (types.ts next to
# migrateSettings.ts in wandb/core). The app's migration moves a shorter
# list under `linePlot` and leaves the rest at the top level of
# `OrganizedSettings`, where the write contract rejects them; the type says
# where they belong.
LINE_PLOT_KEYS = frozenset(
    {
        "colorRunNames",
        "coordinateZooming",
        "displayFullRunName",
        "excludeOutliers",
        "fullFidelityMode",
        "groupAgg",
        "groupingDepth",
        "highlightedCompanionRunOnly",
        "limit",
        "maxRuns",
        "pointVisualizationMethod",
        "showLegend",
        "showOriginalAfterSmoothing",
        "showXRange",
        "singlePointRenderMode",
        "smoothingType",
        "smoothingWeight",
        "stabilizeRunGroups",
        "tooltipNumberOfRuns",
        "useRunsTableGroupingInPanels",
        "windowing",
        "xAxis",
        "xAxisFormat",
        "xAxisMax",
        "xAxisMin",
        "xLogScale",
        "yAxisMax",
        "yAxisMin",
        "yLogScale",
    }
)
# Derived from other settings; the app recomputes them.
DERIVED_KEYS = frozenset(
    {
        "localSmoothingSettingsActive",
        "localxAxisSettingsActive",
        "smoothingActive",
        "xAxisActive",
    }
)
# Deprecated in the app's types with no replacement key to carry a value to.
DEAD_KEYS = frozenset({"showMinMaxOnHover"})

MISSING = object()


def organized_from_legacy(legacy: Dict[str, Any]) -> Dict[str, Any]:
    """`legacy`, a `Settings` block, as `OrganizedSettings`. The two keys the
    write contract no longer accepts are replaced: `ignoreOutliers` by
    `linePlot.excludeOutliers`, `suppressLegends` by `linePlot.showLegend`.
    A block that has both the old and the new key is read from the new."""
    organized: Dict[str, Any] = {}
    line_plot: Dict[str, Any] = {}
    for key, value in legacy.items():
        if key in DERIVED_KEYS or key in DEAD_KEYS or key == "ref" or value is None:
            continue
        if key == "ignoreOutliers":
            if "excludeOutliers" not in legacy:
                line_plot["excludeOutliers"] = (
                    "exclude-outliers" if value else "include-outliers"
                )
        elif key == "suppressLegends":
            if "showLegend" not in legacy:
                line_plot["showLegend"] = not value
        elif key in LINE_PLOT_KEYS:
            line_plot[key] = value
        else:
            organized[key] = value
    if line_plot:
        organized["linePlot"] = line_plot
    return organized


def legacy_from_organized(organized: Dict[str, Any]) -> Dict[str, Any]:
    """`organized`, an `OrganizedSettings` block, as a `Settings` block the
    SDK's internal models read."""
    legacy = {k: v for k, v in organized.items() if k not in ("linePlot", "ref")}
    for key, value in (organized.get("linePlot") or {}).items():
        if key == "excludeOutliers":
            legacy["ignoreOutliers"] = value == "exclude-outliers"
        elif key == "showLegend":
            if value is False:
                legacy["suppressLegends"] = True
        elif key == "pointVisualizationMethod" and value == "sampling-by-default":
            legacy[key] = "sampling"
        else:
            legacy[key] = value
    return legacy


def normalized_legacy(legacy: Dict[str, Any]) -> Dict[str, Any]:
    """`legacy` with the keys the internal models read in place of the ones
    the app writes today: `excludeOutliers` becomes `ignoreOutliers`,
    `showLegend` becomes `suppressLegends`."""
    return legacy_from_organized(organized_from_legacy(legacy))


def has_settings(modern: Any) -> bool:
    """Whether the app reads `modern`, a `workspaceSettings` value, rather
    than migrating the legacy block: it has a key other than `ref`."""
    return isinstance(modern, dict) and any(key != "ref" for key in modern)


Seed = Tuple[Dict[str, Any], Any]


def seed_modern_blocks(spec: Dict[str, Any]) -> List[Seed]:
    """Give `spec`, a loaded spec, the modern settings blocks the app would
    migrate its legacy ones to, wherever the app would do that migration.
    Returns each seed with the value it replaced, for `unseed_untouched`."""
    seeds: List[Seed] = []
    section = spec.get("section")
    if not isinstance(section, dict):
        return seeds
    panel_bank_config = section.get("panelBankConfig") or {}
    modern = section.get("workspaceSettings")
    if not has_settings(modern):
        # The app migrates the panel bank's settings and the legacy block
        # together (parseWorkspaceSpec.ts).
        seed = organized_from_legacy(
            {
                **(panel_bank_config.get("settings") or {}),
                **(section.get("settings") or {}),
            }
        )
        if isinstance(modern, dict) and "ref" in modern:
            seed = {"ref": modern["ref"], **seed}
        seeds.append((seed, section.get("workspaceSettings", MISSING)))
        section["workspaceSettings"] = seed
    for bank_section in panel_bank_config.get("sections") or []:
        if not isinstance(bank_section, dict) or bank_section.get("sectionSettings"):
            continue
        seed = organized_from_legacy(bank_section.get("localPanelSettings") or {})
        seeds.append((seed, bank_section.get("sectionSettings", MISSING)))
        bank_section["sectionSettings"] = seed
    return seeds


def unseed_untouched(spec: Dict[str, Any], seeds: List[Seed]) -> None:
    """Put back what `seed_modern_blocks` replaced wherever `spec`, the spec
    after the edits were applied, still holds the seed itself: the overlay
    returns a loaded value as is when no edit reached it, and a new dict
    when one did."""
    section = spec.get("section")
    if not isinstance(section, dict):
        return
    containers = [section] + [
        s
        for s in (section.get("panelBankConfig") or {}).get("sections") or []
        if isinstance(s, dict)
    ]
    for container in containers:
        for key in ("workspaceSettings", "sectionSettings"):
            if key not in container:
                continue
            for seed, original in seeds:
                if container[key] is seed:
                    if original is MISSING:
                        del container[key]
                    else:
                        container[key] = original
                    break
