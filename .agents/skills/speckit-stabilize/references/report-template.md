# Stabilization Audit & Remediation Report Template

Generate this document at `docs/audit/STABILIZATION_REPORT_<TIMESTAMP>.md` whenever `speckit-stabilize` finds any failing gate, unverified task, security leak, or runtime safety defect.

---

```markdown
# Stabilization Audit & Remediation Report: [FEATURE / RELEASE NAME]

**Audit Timestamp**: YYYY-MM-DD HH:MM:SS  
**Audit Status**: 🛑 BLOCKED (Remediation Required Before Commit/Push)  
**Git Branch**: `[branch-name]`  
**Head Commit**: `[commit-hash]`  
**Feature Directory**: `specs/[feature-dir]`  

---

## 1. Executive Summary

A comprehensive pre-stabilization QA audit was executed across the codebase since the last stabilization baseline. One or more critical verification gates failed or detected residual operational risk. 

**Commit and push are strictly BLOCKED until all pending items listed below are cleanly addressed and certified.**

---

## 2. Gate Verification Summary

| Gate ID | Area / Subsystem | Severity | Status | Output / Reason |
| :--- | :--- | :---: | :---: | :--- |
| `git-diff-check` | Cleanliness & Whitespace | P1 | [PASS / FAIL] | ... |
| `secret-leak-check` | Secret & Runtime File Hygiene | P0 | [PASS / FAIL] | ... |
| `python-syntax-compilation` | Core & Modified Python Files | P0 | [PASS / FAIL] | ... |
| `config-example-alignment` | Schema & Documentation Sync | P2 | [PASS / FAIL] | ... |
| `pytest-regression-suite` | Deterministic Test Suite | P0 | [PASS / FAIL] | ... |
| `windows-nssm-service-health` | Windows Daemon Runtime State | P1 | [PASS / FAIL] | ... |
| `fleet-live-connectivity` | ASIC API 4028 / Summary | P1 | [PASS / FAIL] | ... |
| `speckit-dod-compliance` | Tasks & Development Log Traceability | P2 | [PASS / FAIL] | ... |

---

## 3. Actionable Findings (Pending Remediation Items)

### [FINDING-01]: [Short Descriptive Title]
- **Severity**: P0 (Blocker) | P1 (Critical) | P2 (Hygiene)
- **Affected File(s)**: [`path/to/file.py`](file:///F:/02-ASIC%20-%20mineros/miner-alerts/path/to/file.py#L100-L120)
- **Root Cause & Impact**: Detailed technical explanation of what is wrong or why it is unsafe in production.
- **Required Remediation**: Exact step or code patch needed to resolve this finding.

*(Repeat for each finding)*

---

## 4. Pending Closeout Checklist

The following tasks must be completed and validated before re-running the stabilization skill:

- [ ] **[TASK-01]**: Fix [Finding-01 title] in `path/to/file`.
- [ ] **[TASK-02]**: Run targeted unit/integration tests to verify fix.
- [ ] **[TASK-03]**: Verify Python syntax: `& ".\.venv\Scripts\python.exe" -m py_compile app\miner_monitor.py`.
- [ ] **[TASK-04]**: Re-run full test suite: `& ".\.venv\Scripts\python.exe" -m pytest -q`.
- [ ] **[TASK-05]**: Re-execute `/speckit-stabilize` to certify clean baseline.

---

## 5. Instructions for the Agent / Operator

1. DO NOT bypass this gate by committing manually while P0 or P1 findings remain open.
2. Address each actionable finding sequentially.
3. Once all checklist boxes above are satisfied, run `/speckit-stabilize` again to iterate.
4. When the audit returns `STATUS: PASS`, the stabilization skill will automatically normalize documentation, purge transients, restart the Windows service, and execute the verified commit and push.
```
