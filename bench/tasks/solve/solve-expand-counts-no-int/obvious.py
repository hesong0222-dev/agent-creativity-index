def expand(code):
    out = ""
    i = 0
    while i < len(code):
        letter = code[i]
        j = i + 1
        while j < len(code) and code[j].isdigit():
            j += 1
        out += letter * int(code[i + 1:j])
        i = j
    return out
