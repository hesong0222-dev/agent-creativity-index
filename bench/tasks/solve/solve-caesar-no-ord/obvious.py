def shift(text, k):
    return "".join(chr((ord(c) - 97 + k) % 26 + 97) if "a" <= c <= "z" else c for c in text)
