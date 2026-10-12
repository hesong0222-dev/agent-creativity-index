def is_palindrome(text):
    chars = "".join(filter(str.isalnum, text)).lower()
    return _mirror(chars, 0, len(chars) - 1)


def _mirror(s, i, j):
    if i >= j:
        return True
    return s[i] == s[j] and _mirror(s, i + 1, j - 1)
