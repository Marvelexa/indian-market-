import re

js = open('scratch/app.js', encoding='utf-8').read()

matches = re.findall(r'fetch\([^\)]+\)', js)
print("Fetch calls count:", len(matches))
for m in matches[:30]:
    if '/api/' in m or 'api' in m:
        print("  Fetch:", m[:150])

api_matches = re.findall(r'["\'`](/[^"\'`]*api[^"\'`]*)["\'`]', js)
print("\nAPI paths:", set(api_matches))
