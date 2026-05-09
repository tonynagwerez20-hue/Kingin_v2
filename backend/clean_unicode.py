import re

with open('mt5_account_detector.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace non-ASCII characters
content = re.sub(r'[^\x00-\x7F]+', '', content)

with open('mt5_account_detector.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Unicode characters stripped successfully from mt5_account_detector.py.")
