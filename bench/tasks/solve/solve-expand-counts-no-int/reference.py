def expand(code):
    out = ""
    letter = ""
    count = 0
    for ch in code + "a":
        value = "0123456789".find(ch)
        if value >= 0:
            count = count * 10 + value
        else:
            out += letter * count
            letter, count = ch, 0
    return out
