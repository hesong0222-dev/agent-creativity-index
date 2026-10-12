def _digit(d, one, five, ten):
    return ("", one, one * 2, one * 3, one + five, five, five + one, five + one * 2, five + one * 3, one + ten)[d]


def to_roman(n):
    return ("M" * (n // 1000) + _digit(n // 100 % 10, "C", "D", "M")
            + _digit(n // 10 % 10, "X", "L", "C") + _digit(n % 10, "I", "V", "X"))
