# Reference Captures

Last updated: 2026-07-15

Store each official-application session under `reference_sessions/<UTC timestamp>/`. Never edit the original log after capture; make filtered or annotated copies beside it.

Recommended session contents:

```text
reference_sessions/2026-07-15T000000Z/
├── session.md
├── android-logcat.txt
├── screenshots/
└── extracted-bytes.txt   # only when exact bytes are genuinely present
```

Copy `session-metadata-template.md` to `session.md` at the start of a session. Do not place reconstructed or guessed bytes in `extracted-bytes.txt`; label any later reconstruction separately.

Controlled write validation must be documented separately with the pre-state, exact request and response bytes, immediate readback, rollback/restoration result, and final state. See `reference_sessions/2026-07-15T103257Z/restore-validation.md`.

Captures can contain device identifiers and configuration details. Review them before sharing outside the project.
