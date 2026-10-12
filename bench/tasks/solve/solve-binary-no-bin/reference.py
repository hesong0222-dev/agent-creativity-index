def to_binary(n):
    bits = ""
    while n:
        bits = "01"[n & 1] + bits
        n >>= 1
    return bits or "0"
