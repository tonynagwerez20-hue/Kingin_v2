import sys
try:
    with open('ts_errors.txt', 'r', encoding='utf-16le', errors='ignore') as f:
        print(f.read())
except Exception as e:
    print(e)
