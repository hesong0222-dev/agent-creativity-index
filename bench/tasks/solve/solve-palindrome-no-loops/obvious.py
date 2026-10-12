def is_palindrome(text):
    s = "".join(c for c in text.lower() if c.isalnum())
    return s == s[::-1]
