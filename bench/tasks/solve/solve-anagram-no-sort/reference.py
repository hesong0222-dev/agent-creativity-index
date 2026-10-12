def is_anagram(a, b):
    counts = {}
    for ch in a:
        counts[ch] = counts.get(ch, 0) + 1
    for ch in b:
        counts[ch] = counts.get(ch, 0) - 1
    return not any(counts.values())
