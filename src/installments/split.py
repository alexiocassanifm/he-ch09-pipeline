"""Split an invoice total into equal installments.

The installments add up to the total exactly, none is negative,
and no two installments differ by more than one cent.
"""


def split_amount(total_cents: int, parts: int) -> list[int]:
    if parts < 1:
        raise ValueError("parts must be at least 1")
    if total_cents < 0:
        raise ValueError("total_cents must not be negative")
    base, remainder = divmod(total_cents, parts)
    # The first `remainder` installments carry the leftover cents, one each.
    return [base + 1 if i < remainder else base for i in range(parts)]
