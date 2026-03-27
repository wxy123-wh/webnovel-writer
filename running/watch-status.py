import json, time, os, sys
from datetime import datetime

path = os.path.join(os.path.dirname(__file__), 'feature_list.json')

STATUS_COLOR = {
    'pending':     '\033[90m',
    'claimed':     '\033[33m',
    'in_progress': '\033[36m',
    'done':        '\033[32m',
    'blocked':     '\033[31m',
}
RESET = '\033[0m'
BOLD  = '\033[1m'

def load():
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def render(data):
    features = data['features']
    total   = len(features)
    done    = sum(1 for t in features if t.get('passes') is True)
    inprog  = sum(1 for t in features if t.get('status') == 'in_progress')
    pending = sum(1 for t in features if t.get('status') == 'pending')
    blocked = sum(1 for t in features if t.get('status') == 'blocked')

    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{BOLD}=== webnovel-writer Harness Status ==={RESET}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  {done}/{total} passed  |  {inprog} running  |  {pending} pending  |  {blocked} blocked")
    print()
    print(f"  {'ID':<6} {'Status':<12} {'P':<3} {'MS':<4} {'Title'}")
    print(f"  {'-'*6} {'-'*12} {'-'*3} {'-'*4} {'-'*55}")

    order = {'in_progress': 0, 'claimed': 1, 'pending': 2, 'done': 3, 'blocked': 4}
    for t in sorted(features, key=lambda t: (order.get(t.get('status','pending'), 9), t.get('priority', 99))):
        status = t.get('status', 'pending')
        color  = STATUS_COLOR.get(status, '')
        tick   = '\033[32mv\033[0m' if t.get('passes') else ' '
        title  = t.get('title', '')[:55]
        print(f"  {t['id']:<6} {color}{status:<12}{RESET} {t.get('priority',0):<3} {t.get('milestone',''):<4} {tick} {title}")

    print()
    sessions_dir = os.path.join(os.path.dirname(__file__), 'sessions')
    if os.path.isdir(sessions_dir):
        sessions = sorted(os.listdir(sessions_dir), reverse=True)[:3]
        if sessions:
            print(f"  {BOLD}Recent sessions:{RESET}")
            for s in sessions:
                log = os.path.join(sessions_dir, s, 'codex-output.log')
                last = os.path.join(sessions_dir, s, 'last-message.txt')
                size = f" ({os.path.getsize(log)}b)" if os.path.exists(log) else ''
                snippet = ''
                if os.path.exists(last):
                    try:
                        snippet = open(last, encoding='utf-8', errors='replace').read(100).replace('\n',' ').strip()
                    except Exception:
                        pass
                print(f"    {s}{size}")
                if snippet:
                    print(f"      {snippet}")
    print()
    print("  Ctrl+C to stop.")

interval = int(sys.argv[1]) if len(sys.argv) > 1 else 3
try:
    while True:
        try:
            render(load())
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(interval)
except KeyboardInterrupt:
    print("\nStopped.")
