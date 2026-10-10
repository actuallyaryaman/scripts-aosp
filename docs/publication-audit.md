# Publication audit — 2026-10-10

The GitHub publication file set passed the bundle-aware audit and Gitleaks
8.30.1. The downloaded scanner was verified against the release checksum.
No credential findings remain in the inspected public files.

The scan includes scripts, tests, documentation, JSON manifests, upstream
patches, decoded camera and Separate App Sound payloads, and embedded camera
package baselines. Gitleaks initially flagged two SHA-256 baseline checksums;
only those exact verified values are allowlisted for the generic API-key rule.
Secret values are never included in audit output.

The original bugreport and historical helpers remain private in `diagnostics/`
and `archive/`. They were not copied, staged or published. Git metadata, Python
bytecode, credentials and runtime data are excluded from the publication set.

## Validation

- Ten standalone tests passed: relocation and spaces in paths, explicit root
  precedence, build configuration propagation, output conflicts, exit status,
  mocked uploads, private config permissions, sanitized network errors,
  incompatible feature refusal, payload integrity and publication/index checks.
- Bash and Python syntax checks passed; relative documentation links resolve.
- Camera portability, interface, private ELF and full bundle transaction tests
  passed using the existing checkout and pinned offline donor.
- Separate App Sound bundle transactions and production volume regression passed.
- Cached Treble policy compatibility passed.
- Boot-JAR and labeling tests could not run: the current output log lacks their
  required recorded failure commands. No fresh Android build or flash was run.

The staged-content and Git history audit were also exercised in a temporary
standalone repository containing the public files. No repository was initialized
in the actual toolkit and no remote was created or pushed. GitHub CI is configured
but has not run remotely.

## Limits

This is an audit of the inspected public file set, not a guarantee about ignored
private files, an existing remote, or future edits. Rerun the publication check
and inspect staged content before your first commit; scan real repository history
before pushing. The tools default to VoltageOS. Other ROMs can configure build
and upload settings, but their feature patch compatibility must be checked.
