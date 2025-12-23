
import os

file_path = 'handlers_corrupt.py'

with open(file_path, 'rb') as f:
    content = f.read()

# Detect if it's CRLF CRLF
# On Windows, reading as binary helps see what's there.
# It seems we have excessive newlines.
# Let's try to normalize line endings.

decoded = content.decode('utf-8', errors='ignore')
lines = decoded.splitlines()

# Reconstruct: if we have blank lines between every line, we want to remove them.
# Heuristic: if > 50% of non-empty lines are followed by an empty line, it's likely double spaced.

# However, splitting by lines removes the line endings.
# If we just join them back with '\n', we might lose intentional spacing?
# Let's look at the lines.
# If we have: ["code", "", "code", "", ""] -> ["code", "code", ""]
# This sounds safer than regex replacement on the whole blob.

new_lines = []
skip_next_empty = False

for i, line in enumerate(lines):
    if line.strip() == "":
        # Should we keep it?
        # If the PREVIOUS line was code, and this is empty, and the NEXT is code...
        # If the corruption added an empty line after EVERY line.
        # Then we should skip every ODD empty line?
        pass
    else:
        # non-empty line
        pass

# Simpler approach:
# The corruption likely replaced '\r\n' with '\r\n\r\n' or '\n\n'.
# Let's write a new file where we collapse multiple newlines if they are excessive?
# No, let's just filter out completely empty lines if they appear alternating.

# Let's try: read valid lines.
valid_lines = [line for line in lines if line.strip() != ""]
# This strips ALL empty lines (including paragraphs). This is aggressive but makes the code runnable.
# We can re-add spacing later manually or with a formatter (like black).

with open('handlers_recovered.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(valid_lines))

print(f"Fixed file saved to handlers_recovered.py. Original lines: {len(lines)}, New lines: {len(valid_lines)}")
