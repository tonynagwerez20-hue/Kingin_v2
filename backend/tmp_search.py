import re
import os

def search_dashboard():
    dashboard_path = 'its_dashboard.py'
    if not os.path.exists(dashboard_path):
        print(f"File not found: {dashboard_path}")
        return
        
    with open(dashboard_path, 'rb') as f:
        content = f.read().decode('utf-8', 'ignore')
        
    # Search for terms
    terms = ['ON', 'OFF', 'STATUS', 'LIVE', 'ONLINE', 'OFFLINE']
    pattern = r'.{0,50}(?:' + '|'.join(terms) + r').{0,50}'
    
    matches = re.finditer(pattern, content, re.IGNORECASE)
    
    print(f"--- Dashboard Search Results ({dashboard_path}) ---")
    count = 0
    for match in matches:
        print(f"Match {count + 1}: {match.group(0).strip()}")
        count += 1
        if count >= 30:
            break
            
if __name__ == "__main__":
    search_dashboard()
