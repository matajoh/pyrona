"""Tests for the freezing functionality."""

import pyrona as pr


def test_freezing():
    r2 = pr.Region()
    r3 = pr.Region()
    with r2:
        r2.field = [47, r3]
        with r3:
            r3.field = 11

    x = r2.freeze()
    assert pr.is_imm(x)
    assert r2.is_free
    assert r3.is_free

    with r2:
        try:
            print(r2.field)
        except AttributeError:
            pass
        else:
            raise AssertionError

    with r3:
        try:
            print(r3.field)
        except AttributeError:
            pass
        else:
            raise AssertionError

    print(x)
