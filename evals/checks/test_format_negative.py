from installments import format_cents


def test_negative_small():
    assert format_cents(-5) == "-0.05"


def test_negative_large():
    assert format_cents(-1234) == "-12.34"


def test_positive_unchanged():
    assert format_cents(1234) == "12.34"
    assert format_cents(0) == "0.00"
