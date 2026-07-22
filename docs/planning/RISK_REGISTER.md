# Risk Register

| ID | Risk | Severity | Likelihood | Control | Gate |
| --- | --- | --- | --- | --- | --- |
| R01 | Corrupt or lose `shortcuts.vdf` | Critical | Low | strict parse, stage, verify, rollback, failure injection | every write sprint |
| R02 | Partial artwork set after failure | High | Low | grouped transaction and hash-verified rollback | artwork apply acceptance |
| R03 | Windows-only path/temp failure | High | Current | reproduce and fix current CI failures | Phase 0 |
| R04 | Schema change loses app data | Critical | Medium | database backup, migrations, fixtures, rollback test | before schema v2 |
| R05 | Wrong games merged | High | Medium | no title-only merge, evidence and remembered decisions | identity acceptance |
| R06 | Preferred launch silently changes | High | Medium | multiple recipes and explicit preference | recipe acceptance |
| R07 | Write reaches wrong Steam profile | Critical | Medium | explicit profile in plan and confirmation | apply acceptance |
| R08 | Worker touches UI or app hangs | High | Medium | immutable events, bounded queue, shutdown tests | hardening |
| R09 | Provider outage blocks workflow | Medium | High | cache, partial results, retries, review state | artwork acceptance |
| R10 | Launcher format changes | Medium | High | capability adapters, fixtures, issue codes, non-authoritative failures | each adapter |
| R11 | Installer loses settings/database | High | Medium | upgrade and uninstall matrix on clean VM | alpha release |
| R12 | Logs expose API keys or paths | High | Medium | sanitized diagnostics and secret tests | diagnostics acceptance |
| R13 | UI rewrite bypasses services | High | Medium | isolated read-only proof; dependency review | toolkit decision |
| R14 | Stale docs claim completion | Medium | High | current-state authority and evidence links | every release |
| R15 | Incompatible code/license reuse | High | Medium | license catalog; study before copy | dependency review |
| R16 | No project license creates ambiguity | High | Current | owner chooses root license | pre-alpha |
| R17 | Visual work distracts from blockers | Medium | Current | source-picture phase deferred | owner gate |
