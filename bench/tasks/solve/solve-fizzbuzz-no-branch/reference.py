def fizzbuzz(n):
    out = []
    for i in range(1, n + 1):
        word = "Fizz" * (not i % 3) + "Buzz" * (not i % 5)
        out.append((word, str(i))[not word])
    return out
