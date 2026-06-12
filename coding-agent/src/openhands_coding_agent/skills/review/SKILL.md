---
name: review
description: Post-execution self-review of code changes. Apply after the verify skill has run. Checks requirements, conventions, and test coverage by reading — does not re-run build or tests.
---

# Review

Apply this skill after the `verify` skill has completed. This is a static self-check — read the changes against requirements and domain standards. Do not re-run the build or tests here; that is the `verify` skill's job.

## Before Starting

Check the verification matrix produced by the `verify` skill. If any step is in `failed` state (and not pre-existing), stop — fix that first. Only proceed with review once verify has passed.

## What to Check

### 1. Requirements met
- Re-read the original task description
- Confirm every requirement has been addressed; note anything not done and why
- If versions of dependencies have been specified, check if they are the latest stable versions compatible with the project's existing dependencies. If this is a new project, it should use 
the latest stable versions. You will need to use tools to check for the latest versions, such as npm for JavaScript or NuGet for .NET.

### 2. Domain skill compliance
For each changed file, apply the relevant domain skill:
- `.cs` / `.csproj` / `.sln` → `dotnet-best-practices`
- `.js` / `.jsx` / `.ts` / `.tsx` → `javascript-typescript-best-practices`

Check: naming conventions, code structure, error handling, logging, and any project-specific rules in the domain skill.

### 3. Test coverage
- Every new public method or function has at least one test
- Error paths and edge cases are tested, not just the happy path
- Test names clearly describe what they verify

### 4. No unintended changes
- Review the diff mentally: are there any changes outside the stated scope?
- If yes, note them in the summary — do not silently revert or keep them without comment

### 5. Security (conditional)

Apply this check when the change touches any of: **authentication, authorisation, user input handling, API endpoints, secrets/config, cryptography, file I/O, database queries, or external HTTP calls**.

Skip (and note "security: not applicable") for changes that are purely UI layout, test data, documentation, or build config with no security surface.

For applicable changes, reason about the modified code — do not just pattern-match:

**Injection**
- Are user-supplied values ever passed to SQL queries, shell commands, file paths, or template engines without sanitisation?
- Are ORM methods used correctly (no raw string interpolation in queries)?

**Authentication & authorisation**
- Are new endpoints/routes protected? Are permission checks applied before data access, not just at the route level?
- Are JWTs validated (signature, expiry, claims)? Is there any `alg: none` risk?
- Could a user access or modify another user's data (IDOR/BOLA)?

**Secrets & exposure**
- Are credentials, API keys, or tokens hardcoded or logged?
- Does error output expose stack traces, internal paths, or sensitive data to callers?

**Cryptography**
- Is MD5 or SHA1 used for password hashing or security-relevant digests?
- Are random values used for security (tokens, salts) generated with a CSPRNG?

**Data handling**
- Is user input reflected back to the browser without escaping (XSS)?
- Could an attacker influence a file path or URL to read unintended resources (path traversal, SSRF)?

For each finding: state the file, line range, what the issue is, and the fix. Security findings count against the retry limit the same as any other review failure.

## Output

### Fix-and-retry loop

If any check fails, **fix the issue and re-run verify + review** — do not summarise with known failures. You have up to **5 attempts** total (initial run + 4 retries).

Each retry cycle:
1. Fix all issues identified in the current review
2. Re-run the `verify` skill (build + full tests)
3. Re-run this review from the top

If the review still fails after 5 attempts, emit:

```
ABORT: REVIEW_FAILED

The task was completed but could not pass review after 5 attempts.
The work is on the current branch — the changes have not been reverted.

Unresolved issues:
- [issue]: [what was tried and why it could not be resolved]

To proceed: inspect the branch, resolve the issues manually, then re-submit.
```

### Exceptions

- **Pre-existing failures** (confirmed present before your changes): document in summary, do not count against retry limit, do not ABORT
- **Out-of-scope issues**: note in summary, do not fix silently, do not count against retry limit

A passing review (or an explicit `ABORT: REVIEW_FAILED`) is required before the task is considered complete.
