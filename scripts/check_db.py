import sqlite3
import time

conn = sqlite3.connect('data/miner_alerts.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]
print(f"Total Tables in DB: {len(tables)}")
print("-" * 65)

for t in sorted(tables):
    try:
        cursor.execute(f"SELECT count(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        cursor.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cursor.fetchall()]
        ts_col = next((c for c in cols if 'time' in c.lower() or 'ts' in c.lower() or 'created' in c.lower()), None)
        latest_ts = "N/A"
        if ts_col and cnt > 0:
            cursor.execute(f"SELECT max({ts_col}) FROM {t}")
            val = cursor.fetchone()[0]
            if isinstance(val, (int, float)):
                if val > 1e12:  # milliseconds
                    val = val / 1000.0
                latest_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(val))
            else:
                latest_ts = str(val)
        print(f" - {t:30s}: {cnt:7d} rows | latest: {latest_ts}")
    except Exception as e:
        print(f" - {t:30s}: ERR {e}")
