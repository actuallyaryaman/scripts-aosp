# Publishing rom-tools

The toolkit has no Git repository initialized by this cleanup. Publish only this
folder's eligible files, not the parent ROM checkout.

Install Gitleaks and make `gitleaks` available on PATH. From the toolkit directory:

```bash
python3 scripts/maintenance/publication_check.py --list
python3 scripts/maintenance/publication_check.py --gitleaks
python3 tests/toolkit_test.py
```

The audit rejects unexpected files and symlinks and scans the public sources,
JSON, patches, documentation, decoded camera and Separate App Sound bundles,
and embedded camera package baselines. The two exact checksum allowlist entries
in `.gitleaks.toml` are verified SHA-256 values, not credential patterns.

`diagnostics/` and `archive/` remain private local directories. They are ignored
and excluded from the audited set. Do not force-add them, copy them to a release,
or use an archive of the entire working directory as the publication package.
Credentials, build logs, caches, outputs and transaction backups stay local.

When ready to create a standalone repository:

```bash
git init
git add README.md .gitignore .gitleaks.toml scripts docs tests maintainer .github
python3 scripts/maintenance/publication_check.py --gitleaks --staged
git diff --cached --stat
# Review staged files, then create your initial commit.
```

`--staged` checks index contents as well as current files; it rejects staged
private files and symlinks. After committing, scan history before setting a
remote or pushing:

```bash
python3 scripts/maintenance/publication_check.py --gitleaks --history
```

A passing scan covers inspected publication content and the available local
history. It cannot certify remote history, ignored private data or future edits.
If a real credential is found, remove it from publishable content and revoke it;
removing the current file alone does not remove it from Git history.

CI runs standalone checks, syntax checks and the publication/history audit on
pushes and pull requests. Checkout-dependent Android tests remain local.
