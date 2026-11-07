from installments import split_weighted


def test_sums_exactly():
    for total in (0, 1, 99, 1000, 123457):
        assert sum(split_weighted(total, [1, 2, 3])) == total


def test_proportional():
    assert split_weighted(600, [1, 2, 3]) == [100, 200, 300]


def test_largest_remainder_gets_the_cent():
    # 100 split 1:1:1 is 33.33 each, one cent left over for the first remainder tie.
    parts = split_weighted(100, [1, 1, 1])
    assert sorted(parts) == [33, 33, 34]


def test_zero_weight_gets_nothing():
    assert split_weighted(500, [0, 1]) == [0, 500]
