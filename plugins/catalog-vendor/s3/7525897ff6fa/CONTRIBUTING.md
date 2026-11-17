# Contributing

## Dev setup

1. Clone the repo.
2. Install dependencies:
   ```sh
   pip install boto3 pyyaml
   ```
3. Run the hermetic test suite (no live bucket required):
   ```sh
   python3 scripts/test-s3-backup.py
   ```
   The suite exits 0 on success.

## Making changes

- Keep code changes minimal and focused. Add or update tests for any changed behaviour.
- Match the JSON output contract (`{"ok": bool, ...}`) for all commands.
- Do not add credentials, bucket names, or endpoint URLs to any tracked file.

## Pull requests

- One logical change per PR.
- Tests must pass (`python3 scripts/test-s3-backup.py`).
- Update `README.md` if you change CLI flags, rules format, or configuration variables.
- Commit messages should be concise and imperative ("Add --force to pull", not "Added").
