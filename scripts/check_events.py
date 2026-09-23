import sqlite3
import time

conn = sqlite3.connect('data/miner_alerts.db')
c = conn.cursor()
ts_threshold = time.time() - 7200  # last 2 hours

print('=== OPERATIONAL EVENTS (Last 2 hours) ===')
c.execute('SELECT event_type, miner_name, occurred_ts, summary FROM operational_events WHERE occurred_ts >= ? ORDER BY occurred_ts DESC LIMIT 30', (ts_threshold,))
rows = c.fetchall()
if not rows:
    print("No operational events in the last 2 hours.")
for r in rows:
    t_str = time.strftime('%H:%M:%S', time.localtime(r[2]))
    print(f"[{t_str}] {r[0]:25s} {str(r[1]):15s} {str(r[3])[:70]}")

print('\n=== REBOOT DECISIONS (Last 2 hours, non-NO_ACTION) ===')
c.execute("SELECT result, miner_name, evaluated_ts, state FROM reboot_decisions WHERE evaluated_ts >= ? AND result != 'NO_ACTION' ORDER BY evaluated_ts DESC LIMIT 30", (ts_threshold,))
rows = c.fetchall()
if not rows:
    print("No non-NO_ACTION reboot decisions in the last 2 hours.")
for r in rows:
    t_str = time.strftime('%H:%M:%S', time.localtime(r[2]))
    print(f"[{t_str}] {r[0]:25s} {str(r[1]):15s} state={str(r[3])}")

