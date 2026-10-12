def add(a, b):
    while b:
        carry = (a & b) << 1
        a = a ^ b
        b = carry
    return a
