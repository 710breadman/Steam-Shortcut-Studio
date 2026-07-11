# Transaction Service Specification

## Objective

Create one tested boundary for every operation that changes Steam-owned files. UI code may build, approve, and display plans, but it must not write Steam files directly.

## Core Stages

```text
DISCOVER
  -> PLAN
  -> VALIDATE
  -> BACKUP
  -> APPLY
  -> READ_BACK
  -> VERIFY
  -> COMMIT_HISTORY

Any failure after BACKUP:
  -> ROLLBACK
  -> VERIFY_RESTORE
  -> RECORD_FAILURE
```

## Existing Contract Foundation

`steam_shortcut_studio/transactions.py` defines:

- `ChangeKind`
- `ChangeAction`
- `RiskLevel`
- `PlannedChange`
- `TransactionPlan`
- `VerificationResult`
- `TransactionResult`

These classes define scope and approval only. They do not write files.

## Service Boundary

Future service interface:

```python
class TransactionService:
    def prepare(plan: TransactionPlan) -> PreparedTransaction: ...
    def apply(prepared: PreparedTransaction) -> TransactionResult: ...
    def rollback(transaction_id: str) -> TransactionResult: ...
    def verify(transaction_id: str) -> list[VerificationResult]: ...
```

## Plan Rules

- Every change references a stable library item ID.
- Every change identifies one exact target path or logical target.
- Risk level is explicit.
- Safe changes may be approved in bulk.
- Review/advanced changes require explicit approval.
- The active inspector row never changes batch scope.
- A plan is immutable after preparation; edits produce a new plan/version.

## Preparation

Preparation must:

- Resolve all target paths.
- Confirm the target belongs to the selected Steam profile.
- Reject paths inside game installation directories.
- Compute original file existence, size, timestamp, and hash.
- Stage complete replacement data in an app-owned transaction directory.
- Decode and validate staged artwork.
- Parse staged VDF before apply.
- Estimate required Steam shutdown.
- Produce a human-readable preview.

## Backup

- Backups are grouped by transaction ID.
- Preserve original relative paths.
- Record SHA-256 hashes.
- Do not overwrite prior transaction backups.
- If a target does not exist, record that rollback should delete the newly created target.
- A transaction is not ready until every required backup succeeds.

Suggested location:

```text
<AppData>/SteamShortcutStudio/transactions/<transaction-id>/
  plan.json
  manifest.json
  staged/
  backups/
  result.json
```

## Apply

- Close Steam only if an approved change requires it.
- Confirm shutdown before writing.
- Apply staged files with same-volume temporary replacement where possible.
- Do not continue to later change groups after a required write fails.
- Optional changes may fail individually only when the plan explicitly permits partial success.

## Verification

### Shortcuts

- Parse the written binary VDF.
- Confirm every expected record and owned field.
- Confirm preserved fields remain unchanged.
- Confirm unrelated records remain present.

### Artwork

- Confirm every intended target exists.
- Confirm hash equals the staged source.
- Decode the copied file.
- Confirm no unintended slot variants were deleted.

### Compatibility mapping

- Parse the written text VDF.
- Confirm exact selected AppID mappings.
- Confirm unrelated mappings remain unchanged.

### Notes

- Parse generated JSON where applicable.
- Confirm user-authored text is preserved.
- Confirm native Steam entries were not written unless later explicitly supported.

## Rollback

Rollback must:

- Restore every original file from the grouped backup.
- Delete targets that did not exist before the transaction.
- Verify restored hashes and parsing.
- Record partial restore failures prominently.
- Reopen Steam only after restore verification when the app originally closed it.

## Malformed Input Policy

A malformed Steam-owned file is not silently replaced.

Default behavior:

1. Abort.
2. Preserve the original in place.
3. Offer diagnostics and backup/export.
4. Offer explicit advanced recovery only after warning that unparsed records cannot be preserved.

## History

Store:

- Transaction ID and timestamps
- App version
- Steam profile ID
- Selected library IDs
- Plan and approvals
- Original/staged/written hashes
- Backup paths
- Apply/verification/rollback results
- Errors

API keys and unnecessary personal paths should not be written to history.

## Tests Required

- Successful shortcut add/update
- Preserved unrelated shortcut records
- Preserved unknown supported fields
- Malformed VDF abort
- Write failure before replace
- Verification failure and automatic restore
- Artwork multi-slot partial-copy failure
- Compatibility mapping read-back failure
- New-file rollback deletion
- Existing-file restore
- Steam was running versus not running
- Repeated rollback idempotence

## Integration Order

1. Wrap `shortcuts.vdf` only.
2. Add transaction history.
3. Add artwork as a grouped file set.
4. Add compatibility mapping.
5. Add generated notes.
6. Remove direct UI calls to legacy write functions.

## Acceptance Criteria

- No UI event handler writes Steam-owned files directly.
- Every Steam write has a persisted plan and backup manifest.
- Verification failures restore automatically.
- Restore verification is recorded.
- Existing smoke behavior remains covered.
