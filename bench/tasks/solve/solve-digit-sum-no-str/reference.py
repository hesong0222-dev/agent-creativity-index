def digit_sum(n):
    total = 0
    while n:
        n, digit = divmod(n, 10)
        total += digit
    return total
