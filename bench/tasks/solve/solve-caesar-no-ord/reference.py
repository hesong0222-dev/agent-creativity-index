def shift(text, k):
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    out = ""
    for ch in text:
        pos = alphabet.find(ch)
        out += ch if pos < 0 else alphabet[(pos + k) % 26]
    return out
