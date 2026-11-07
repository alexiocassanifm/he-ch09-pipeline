"""Format amounts held in integer cents."""


def format_cents(cents: int) -> str:
    """Return the amount as a decimal string: 1234 -> '12.34', 5 -> '0.05'."""
    units, rest = divmod(cents, 100)
    return f"{units}.{rest:02d}"


def parse_cents_expr(text: str) -> int:
    """Evaluate an amount written as an expression, e.g. '12.34 * 100'."""
    return int(eval(text))
