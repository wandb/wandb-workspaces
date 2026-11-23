"""The harness's own diff, since the round-trip tests and the report trust it."""

from .spec_harness import diff_specs


def test_identical_specs_have_no_differences():
    spec = {"section": {"runSets": [{"id": "rs1", "enabled": True}], "n": 0}}
    diff = diff_specs(spec, spec)
    assert diff.is_lossless and not diff.added
    assert diff.summary() == "no differences"


def test_a_dropped_object_counts_once_at_its_own_path():
    diff = diff_specs({"a": {"deep": {"deeper": 1}}, "b": 1}, {"b": 1})
    assert diff.dropped == [("a",)]
    assert not diff.added and not diff.changed


def test_an_added_object_counts_once_at_its_own_path():
    diff = diff_specs({"b": 1}, {"a": {"deep": 1}, "b": 1})
    assert diff.added == [("a",)]
    assert diff.is_lossless


def test_a_changed_scalar_is_reported_at_its_path():
    diff = diff_specs({"s": {"x": 1, "y": "a"}}, {"s": {"x": 2, "y": "b"}})
    assert diff.changed == [("s", "x"), ("s", "y")]


def test_a_number_that_only_changes_type_is_not_a_change():
    diff = diff_specs({"min": 0, "max": 1.5}, {"min": 0.0, "max": 1.5})
    assert diff.is_lossless and not diff.added


def test_a_boolean_and_a_number_are_different_values():
    diff = diff_specs({"on": True, "n": 1}, {"on": 1, "n": True})
    assert diff.changed == [("n",), ("on",)]


def test_a_value_that_changes_json_type_is_a_change():
    diff = diff_specs({"a": {"k": 1}, "b": [1], "c": 1}, {"a": [1], "b": 1, "c": "1"})
    assert diff.changed == [("a",), ("b",), ("c",)]


def test_null_is_a_value():
    diff = diff_specs({"a": None, "b": 0}, {"a": 0, "b": None})
    assert diff.changed == [("a",), ("b",)]


def test_lists_are_compared_by_position():
    diff = diff_specs(
        {"l": [{"id": 1}, {"id": 2}, {"id": 3}]},
        {"l": [{"id": 1}, {"id": 9}, {"id": 3}, {"id": 4}]},
    )
    assert diff.changed == [("l", 1, "id")]
    assert diff.added == [("l", 3)]
    assert not diff.dropped


def test_a_shortened_list_drops_the_trailing_items():
    diff = diff_specs({"l": [1, 2, 3]}, {"l": [1]})
    assert diff.dropped == [("l", 1), ("l", 2)]


def test_summary_lists_each_kind_and_caps_the_paths():
    diff = diff_specs({f"k{i}": i for i in range(3)}, {"new": 1})
    text = diff.summary(limit=2)
    assert text.splitlines()[0] == "3 dropped:"
    assert "... and 1 more" in text
    assert "1 added:" in text and "  .new" in text
