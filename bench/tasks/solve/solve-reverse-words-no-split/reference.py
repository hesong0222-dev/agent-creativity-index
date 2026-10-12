def reverse_words(text):
    words = []
    current = ""
    for ch in text + " ":
        if ch == " ":
            if current:
                words.insert(0, current)
            current = ""
        else:
            current += ch
    return " ".join(words)
