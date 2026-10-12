def transpose(matrix):
    if not matrix:
        return []
    width = len(next(iter(matrix)))
    rows = list(map(iter, matrix))
    return [list(map(next, rows)) for _ in range(width)]
