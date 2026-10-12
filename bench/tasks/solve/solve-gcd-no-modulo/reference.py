def gcd(a, b):
    shift = 0
    while not (a | b) & 1:
        a >>= 1
        b >>= 1
        shift += 1
    while a != b:
        while not a & 1:
            a >>= 1
        while not b & 1:
            b >>= 1
        if a > b:
            a, b = b, a
        if a != b:
            b -= a
    return a << shift
