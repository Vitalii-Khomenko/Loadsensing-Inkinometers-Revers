# Repository Language Policy

This policy applies to the entire repository tree unless a more specific `AGENTS.md` explicitly strengthens it.

## Mandatory language

All project-authored content must be written in English only, regardless of the language used in a request or discussion.

This includes:

- source code identifiers, constants, classes, functions, variables, and filenames;
- comments, docstrings, type descriptions, and TODO/FIXME notes;
- user-interface labels, help text, validation messages, errors, warnings, logs, and exported column names;
- API field descriptions and human-readable API responses;
- tests, fixtures authored by this project, assertions, and test names;
- Markdown documentation, command references, roadmap entries, and examples;
- configuration templates, machine-readable registries, and generated project reports.

Do not add Cyrillic or any other non-English prose to maintained project files. Translate user-provided wording into clear technical English before storing it.

## Protocol and evidence exceptions

Do not modify immutable third-party or captured evidence merely to satisfy the language policy. The following may preserve original bytes or vendor content:

- decompiled APK output under `analysis/jadx/` and `analysis/apktool/`;
- original packages and firmware evidence under `analysis/original/`;
- raw captures and imported evidence under `captures/`;
- exact protocol byte strings, vendor identifiers, product names, and quoted source literals.

Project-authored documentation surrounding that evidence must still be English.

## Requested localized stakeholder reports

When the user explicitly requests a report for colleagues in another language, it may be stored under `reports/localized/`. This exception applies only to non-technical stakeholder reports. Code, UI, APIs, operator instructions, technical documentation, tests, filenames, and the roadmap remain English.

## Required validation

Before completing a change, run:

```bash
/usr/bin/python3 -m pytest -q tests
/usr/bin/python3 -m compileall -q tools tests
```

The language-policy tests must remain enabled. If they detect non-English authored content, translate it rather than weakening the scan or adding an exclusion. New exclusions are allowed only for immutable external evidence and must be documented in this file.
