import sys
sys.path.insert(0, ".")
import json
from app.vnish import safe_get_overclock_settings, get_miner_status

miners = [
    ("S19JPRO-23", "192.168.100.23"),
    ("S19JPRO-24", "192.168.100.24"),
    ("S19JPRO-25", "192.168.100.25"),
    ("S19JPRO-26", "192.168.100.26"),
]

for name, host in miners:
    ok, oc, err = safe_get_overclock_settings(host, "admin")
    ok_st, st, err_st = get_miner_status(host, timeout=2.0)
    top_p = oc.get("top_preset") if ok and oc else None
    preset = oc.get("preset") if ok and oc else None
    state = st.get("miner_state") if ok_st and st else None
    print(f"[{name}] host={host} state={state} preset={preset} top_preset={top_p}")
