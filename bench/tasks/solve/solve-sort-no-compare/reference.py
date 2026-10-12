def sort_numbers(nums):
    counts = [0] * 1001
    for n in nums:
        counts[n] += 1
    out = []
    for value, count in enumerate(counts):
        out.extend([value] * count)
    return out
