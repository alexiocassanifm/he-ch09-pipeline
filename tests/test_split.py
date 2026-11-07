import pytest

from installments import split_amount


def test_even_split():
    assert split_amount(900, 3) == [300, 300, 300]


def test_leftover_cents_go_first():
    assert split_amount(1000, 3) == [334, 333, 333]


def test_rejects_zero_parts():
    with pytest.raises(ValueError):
        split_amount(100, 0)
