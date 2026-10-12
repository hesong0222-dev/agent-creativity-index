def balanced(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = ""
    for ch in s:
        if ch in "([{":
            stack += ch
        elif ch in pairs:
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack = stack[:-1]
    return not stack
