# Tasks: Valid Signal Auto-Reboot Gate

- [x] T001 Identify the unsafe fall-through from invalid/recovered signal into LOW action evaluation.
- [x] T002 Specify exact eligible, invalid, and recovered behavior.
- [x] T003 Implement pure finite-signal classifier.
- [x] T004 Place classifier as outer auto-reboot gate without changing state transitions.
- [x] T005 Audit/log invalid signal exactly once and clear sustained LOW timing.
- [x] T006 Audit/log recovered/non-LOW signal exactly once and clear sustained LOW timing.
- [x] T007 Preserve the existing eligible gate chain and post-policy processing.
- [x] T008 Add deterministic unit and policy wiring tests.
- [x] T009 Run py_compile, full unit suite, diff check, and Speckit QA.
- [x] T010 Update evidence, development log, roadmap, commit, and push without service restart.
