"""The live key must not show up in pytest's failure output. Runs in every pytest run (no ``live`` mark, no key)."""

from __future__ import annotations

import pytest

from tests.contract_shapes import is_legacy_key

from .conftest import LiveKey

SECRET = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"  # shaped like a legacy key; not one that was ever issued


def test_the_redacted_key_still_works_as_a_value():
    key = LiveKey(SECRET)
    assert str(key) == SECRET
    assert f"{key}" == SECRET
    assert key == SECRET
    assert is_legacy_key(key)
    assert isinstance(key, str)


def test_repr_does_not_contain_the_key():
    assert SECRET not in repr(LiveKey(SECRET))
    assert SECRET not in f"{LiveKey(SECRET)!r}"


def test_assertion_introspection_does_not_print_the_key():
    """This module is assertion-rewritten, so the message carries the operands the way a failed report would."""
    key = LiveKey(SECRET)
    with pytest.raises(AssertionError) as caught:
        assert not is_legacy_key(key)
    assert SECRET not in str(caught.value)
    with pytest.raises(AssertionError) as plain:
        assert not is_legacy_key(SECRET)  # control: a plain str is printed, so the test above proves something
    assert SECRET in str(plain.value)
