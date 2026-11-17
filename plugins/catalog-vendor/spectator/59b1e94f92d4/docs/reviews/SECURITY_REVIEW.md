# Adversarial Security and Correctness Review: Duckwork Spectator Plugin

## Summary

Review of `src/spectator/feed/engine.py` and `src/spectator/db/db.py` for privacy mask bypasses, fail-closed paths, SQL injection, cursor/reset logic issues, and dangerous functions.

## Findings

### MEDIUM: Potential Privacy Mask Bypass via Mixed-Case Environment Variables
- **Location**: `engine.py:101` (`_ENV_VAR_RE`) and `engine.py:107-110` (`_SECRET_KEY_RE`)
- **What can go wrong**: Environment variable names with mixed case after the first character (e.g., `PaSsWoRd=secret`) would not be matched by the uppercase env-var regex (`[A-Z][A-Z0-9_]{2,}=`) because it requires all characters after the first to be uppercase, digits, or underscore. However, the secret key assignment regex would catch this due to case-insensitive matching.
- **Impact**: Potential leakage of environment variable values that could contain secrets, passwords, or sensitive configuration.
- **Recommendation**: The current implementation is actually safe because the `_SECRET_KEY_RE` pattern (case-insensitive) catches common secret key names regardless of case. However, for completeness and consistency, consider making the `_ENV_VAR_RE` pattern case-insensitive as well, or document why the distinction exists.

### LOW: Potential Race Condition in Cursor Reset Logic
- **Location**: `engine.py:354-387` (query method)
- **What can go wrong**: Between the time the oldest sequence number is fetched (line 355-358) and when the reset query is executed (line 377), events could be deleted by a concurrent sweep operation, causing the reset to return events that no longer exist or altering the expected behavior.
- **Impact**: Degraded UX - guests might receive incorrect reset behavior or missing events. Not a security issue as it doesn't lead to data leakage or corruption.
- **Recommendation**: Consider performing the oldest sequence check and the query execution within the same transaction or using a more robust stale cursor detection mechanism.

### LOW: URL Decoding Only Applied Once
- **Location**: `engine.py:191-193` (URL decoding steps)
- **What can go wrong**: The function applies URL decoding (`%2F` → `/`, `%5C` → `\`) only once. Double URL-encoded paths (e.g., `%252F` which decodes to `%2F` then to `/`) would not be fully decoded and might bypass path detection.
- **Impact**: Potential leakage of file paths if double-encoded paths are used in contexts where they get decoded later by downstream systems.
- **Recommendation**: Consider applying URL decoding iteratively until no more percent-encoded sequences remain, or use a proper URL decoding function.

### LOW: Base64 Token Regex Might Match Non-Base64 Strings
- **Location**: `engine.py:82` (`_BASE64_TOKEN_RE = re.compile(r'[A-Za-z0-9+/=]{8,200}')`)
- **What can go wrong**: The regex matches any string of 8-200 characters consisting only of A-Z, a-z, 0-9, +, /, and =. This could potentially match non-base64 strings that happen to fit this pattern, causing unnecessary processing (though not a security bypass).
- **Impact**: Minimal performance impact only.
- **Recommendation**: Consider adding more strict base64 validation (checking for proper padding) if performance becomes a concern.

## No Issues Found

### SQL Injection
- **Status**: None found
- **Explanation**: All database queries in both files use parameterized queries with `?` placeholders. No string formatting or concatenation is used in SQL query construction.

### Dangerous Functions (eval/exec/shell-out)
- **Status**: None found
- **Explanation**: No instances of `eval`, `exec`, `compile`, `__import__`, `open`, `os.system`, `os.popen`, or `subprocess` calls were found in either file.

### Fail-closed Paths
- **Status**: Properly implemented
- **Explanation**: The `privacy_mask` and `mask_summary` functions both have try-except blocks that return `[redacted]` on any exception, following a fail-closed design.

## Conclusion

The Spectator plugin demonstrates good security practices overall with proper use of parameterized queries, fail-closed error handling, and comprehensive privacy masking. The identified issues are mostly low-risk and relate to edge cases in the privacy masking logic and a potential race condition in cursor handling that could affect user experience but not lead to security vulnerabilities.

The mixed-case environment variable detection appears to be adequately covered by the secret key assignment regex, so no immediate action is required for the MEDIUM finding.