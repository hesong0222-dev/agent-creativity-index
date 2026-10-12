def count_vowels(text):
    return sum(text.lower().count(v) for v in "aeiou")
