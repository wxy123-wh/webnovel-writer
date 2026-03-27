import json
from datetime import datetime

path = r'd:\code\webnovel-writer\running\feature_list.json'
with open(path, encoding='utf-8') as f:
    data = json.load(f)

now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
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
        note = '[RESET %s] Reset from in_progress to pending for fresh dispatch.' % now
        existing = t.get('notes', '')
        t['notes'] = (existing + '\n' + note).strip() if existing else note
        print('Reset', t['id'])

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
print('Done')
