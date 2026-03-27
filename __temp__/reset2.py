import json, re

path = r'd:\code\webnovel-writer\running\feature_list.json'
with open(path, encoding='utf-8') as f:
    data = json.load(f)

count = 0
for t in data['features']:
    if t.get('passes') is not True and t.get('status') != 'done':
        t['status'] = 'pending'
        t['claimed_by'] = ''
        t['claimed_at'] = ''
        t['started_at'] = ''
        t['completed_at'] = ''
        t['blocked_reason'] = ''
        t['human_help_requested'] = False
        t['handoff_requested_at'] = ''
        count += 1
        print(f"Reset {t['id']} -> pending")

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
print(f'Done: reset {count} tasks')
