import requests
import re

js = requests.get('https://dummytrader.in/assets/app-CEoxk-ki.js').text
open('scratch/app.js', 'w', encoding='utf-8').write(js)
print('app.js size:', len(js))

apis = set(re.findall(r'["\'`]/api/v1/[a-zA-Z0-9_\-/]+["\'`]', js))
print('APIs found in app.js:')
for a in sorted(apis):
    print("  ", a)

# Let's search for "order" or error messages in app.js
errors = set(re.findall(r'error[s]?:?\s*["\'`][^"\'`]{5,60}["\'`]', js, re.IGNORECASE))
print('\nErrors found:')
for e in list(errors)[:20]:
    print("  ", e)
