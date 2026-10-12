def unique(items):
    seen = {}
    out = []
    for item in items:
        if item not in seen:
            seen[item] = True
            out.append(item)
    return out
