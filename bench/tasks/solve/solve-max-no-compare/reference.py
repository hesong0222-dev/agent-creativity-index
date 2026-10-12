def largest(values):
    best = values[0]
    for v in values[1:]:
        best = (best + v + abs(best - v)) // 2
    return best
