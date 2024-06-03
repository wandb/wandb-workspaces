from collections.abc import MutableMapping


class InvertableDict(MutableMapping):
    """A bijective mapping that behaves like a dict.

    Invert the dict using the `inv` property.
    """

    def __init__(self, *args, **kwargs):
        self._forward = dict(*args, **kwargs)
        self._backward = {}
        for key, value in self._forward.items():
            if value in self._backward:
                raise ValueError(f"Duplicate value found: {value}")
            self._backward[value] = key

    def __getitem__(self, key):
        return self._forward[key]

    def __setitem__(self, key, value):
        if key in self._forward:
            del self._backward[self._forward[key]]
        if value in self._backward:
            raise ValueError(f"Duplicate value found: {value}")
        self._forward[key] = value
        self._backward[value] = key

    def __delitem__(self, key):
        value = self._forward.pop(key)
        del self._backward[value]

    def __iter__(self):
        return iter(self._forward)

    def __len__(self):
        return len(self._forward)

    def __repr__(self):
        return repr(self._forward)

    def __contains__(self, key):
        return key in self._forward

    @property
    def inv(self):
        return self._backward
