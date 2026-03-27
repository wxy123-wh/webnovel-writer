import json

path = r'd:\code\webnovel-writer\running\feature_list.json'
with open(path, encoding='utf-8') as f:
    data = json.load(f)

for t in data['features']:
    if t.get('passes') is not True:
        t['status'] = 'pending'
        t['claimed_by'] = ''
        t['claimed_at'] = ''
        t['started_at'] = ''
        t['completed_at'] = ''
        t['blocked_reason'] = ''
        t['human_help_requested'] = False
        t['handoff_requested_at'] = ''
        t['defer_to_tail'] = False
        t['failure_count'] = 0
        t['last_failure_summary'] = ''
        t['requeued_at'] = ''
        t['notes'] = '[RESET 2026-03-28] Ready for dispatch.'

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print('Done')
for t in data['features']:
    print(t['id'], t['status'])
