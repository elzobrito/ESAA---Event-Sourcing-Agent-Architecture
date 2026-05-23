# Behavioral Critical Audit Contract

The critical audit must check behavior-facing markers, not only file presence.

Required coverage:

- plugin dispatch parity between `eligible` and `run`;
- dry-run responses with explicit `status=dry_run` and simulated append metadata;
- recoverable file effects with content-addressed artifacts;
- hotfix validation before `hotfix.create`;
- `issue.report` preserving `prior_status=done`;
- baseline lessons reseeded by replayable events;
- independent QA review policy.

Passing audit means `src/audit/critical_findings.py --root .` returns zero
findings.
