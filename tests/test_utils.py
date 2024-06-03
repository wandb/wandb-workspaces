import pytest

from wandb_workspaces.utils.invertable_dict import InvertableDict


def test_invertible_dict_cant_init_with_duplicates():
    with pytest.raises(ValueError):
        d = InvertableDict({"a": 1, "b": 2, "c": 2})  # noqa: F841


def test_invertible_dict_updates_backmapping_on_key_overwrite():
    d = InvertableDict({"a": 1, "b": 2, "c": 3})

    d["a"] = 4
    assert (
        1 not in d.inv
    ), "Old value should not be in inverted dict if key is overwritten"


def test_invertible_dict_cant_add_duplicates():
    d = InvertableDict({"a": 1, "b": 2, "c": 3})

    with pytest.raises(ValueError):
        d["d"] = 1


def test_invertible_dict_deletion():
    d = InvertableDict({"a": 1, "b": 2, "c": 3})

    del d["a"]
    assert len(d) == 2, "Length should be updated"
    assert d.keys() == {"b", "c"}, "Keys should be updated"
    assert d.inv.keys() == {2, 3}, "Inverted keys should be updated"


def test_invertible_dict_is_dictlike():
    d = {"a": 1, "b": 2, "c": 3}
    d2 = InvertableDict(d)

    for k1, k2 in zip(d, d2):
        assert k1 == k2, "Keys should match"

    for v1, v2 in zip(d.values(), d2.values()):
        assert v1 == v2, "Values should match"

    for (k1, v1), (k2, v2) in zip(d.items(), d2.items()):
        assert k1 == k2, "Keys should match"
        assert v1 == v2, "Values should match"

    assert len(d) == len(d2), "Lengths should match"

    assert "a" in d2, "Key should be in dict"
    assert 1 in d2.inv, "Value should be key in inverted dict"

    assert repr(d) == repr(d2)
