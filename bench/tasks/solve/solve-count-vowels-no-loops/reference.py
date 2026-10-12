def count_vowels(text):
    return len(list(filter(lambda c: c in "aeiou", text.lower())))
