with open('its_dashboard.py', 'rb') as f:
    content = f.read().decode('utf-8', 'ignore')
with open('its_dashboard_clean.py', 'w', encoding='ascii', errors='ignore') as f2:
    f2.write(content)
print("File cleaned successfully.")
