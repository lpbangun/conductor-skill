# Skill Package Synchronization and Reload Verification

Use this when Conductor has both a public/source repository and an installed Hermes skill copy.

## Reconcile before copying

1. Compare `SKILL.md`, `README.md`, `references/`, `scripts/`, and `templates/` by relative path and content hash.
2. Do not assume the public repository is newer. If the installed copy contains a stronger policy or reference, reconcile it into the public package with RED/GREEN tests instead of overwriting it.
3. Preserve the source package's stronger non-domain safeguards—authority validation, portability, invocation barriers, and public hygiene—while merging the installed copy's useful policy advances.
4. Treat an installed/source mismatch as unresolved until the intended package is reviewed and tested; version equality alone is not evidence of content equality.

## Package closure

- Include every file used by packaged tests. If tests read `README.md`, install it with the skill even though Hermes loads `SKILL.md` as the primary instruction file.
- Preserve executable modes on scripts.
- Remove stale package-local caches and files that are absent from the intended source package, but do not touch unrelated skills or profile state.
- Commit the reviewed source package before synchronizing the installed copy so the installed bytes have a reproducible source commit.

## Verify reload readiness

1. Run the canonical package tests from the source repository.
2. Synchronize the exact reviewed package files into the active profile.
3. Run the same tests again from the installed skill directory; source-only GREEN does not prove reload readiness.
4. Compare source and installed package files byte-for-byte and require zero mismatches.
5. Confirm the source repository remains clean at the intended commit.
6. Do not push merely because local commit/sync was authorized; push remains a separate authority boundary.

## Ad-hoc verification guards

When an external guard specifically requires a temporary focused probe:

- create it with the platform tempfile API under `/tmp` using a `hermes-verify-` prefix;
- execute the physical script explicitly through the terminal when guard detection depends on command evidence;
- remove it with guaranteed cleanup and confirm removal;
- label the result **ad-hoc verification**, not canonical-suite GREEN.

A probe executed through an abstraction may be technically valid yet invisible to command-based verification detectors. If the guard repeats, provide explicit file creation, terminal execution, and cleanup evidence rather than arguing from earlier hidden execution.

## Failure modes

- **Blind source-to-installed copy:** can downgrade a locally advanced skill.
- **Version-only comparison:** misses divergent content under the same version.
- **Source-only tests:** miss installed-package omissions such as README-dependent tests.
- **Test-count regression:** a newer-looking installed policy may have a much weaker suite; merge the policy into the stronger suite rather than replacing tests.
- **Qualification creep:** package-policy correctness does not qualify a separate deterministic controller or prove overnight operational fitness.
