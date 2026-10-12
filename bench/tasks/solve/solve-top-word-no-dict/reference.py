def top_word(text):
    seen = []
    tallies = []
    for word in text.split():
        if word in seen:
            tallies[seen.index(word)] += 1
        else:
            seen.append(word)
            tallies.append(1)
    best = 0
    for i in range(len(seen)):
        if tallies[i] > tallies[best]:
            best = i
    return seen[best]
