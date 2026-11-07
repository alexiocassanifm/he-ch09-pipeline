from installments import format_cents


def test_formats_whole_and_fraction():
    assert format_cents(1234) == "12.34"


def test_pads_small_amounts():
    assert format_cents(5) == "0.05"
