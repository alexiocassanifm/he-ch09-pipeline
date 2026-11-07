from installments import parse_cents


def test_euro_suffix():
    assert parse_cents("12,34 €") == 1234


def test_thousands_separator_and_prefix():
    assert parse_cents("€ 1.234,56") == 123456


def test_negative():
    assert parse_cents("-0,05") == -5
