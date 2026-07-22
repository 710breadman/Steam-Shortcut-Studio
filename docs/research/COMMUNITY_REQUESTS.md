# Community Request Evidence

Initial evidence comes from public Steam ROM Manager issues and comparable-project workflows. Broader Reddit, Steam Community, Bazzite, and video research remains a later research pass.

| Need | Evidence level | Product fit | Priority | Decision |
| --- | --- | --- | --- | --- |
| Reliable backup and restore | Repeated/high impact | Core safety | P0 | Build complete restore workflow |
| Recover partially valid imports instead of failing all | Repeated | Reliability | P0 | Apply tolerant read/import policy where safe |
| Avoid duplicate/uncategorized entries | Repeated | Identity/reconciliation | P0 | Covered by identity phases |
| Artwork filter by slot/type | Repeated | Artwork efficiency | P1 | Add after review workflow |
| Artwork filter by platform | Repeated | Match accuracy | P1 | Add provider filter |
| Prefer language per source/parser | Repeated | Match accuracy | P2 | Add configurable preference |
| Prefer cohesive artwork author/style | Isolated but useful | Visual coherence | P2 | Revisit after core |
| Custom Steam executable/root path | Repeated | Setup correctness | P0 | Include first-run and settings |
| Linux ICO conversion | Repeated platform pain | Linux support | P2 | Add during SteamOS/Bazzite phase |
| Programmatic configuration import/export | Repeated power-user need | Portability/support | P2 | Add after schema stability |
| Compatibility-tool/Proton control | Repeated | SteamOS/Bazzite | Deferred | Keep read-only until ownership/rollback proven |
| Automatic decompression | Isolated/high maintenance | Weak product fit | Reject for core | Leave to launcher/emulator tools |
| Explorer “Add to Steam” | Owner/community idea | Strong Windows QoL | P1 | Open review flow; never silent write |
| Games found but not added | Owner/community idea | Strong smart view | P1 | Build from explicit Steam state |
| Notes and tags | Repeated | Strong library value | P1 | Structured app notes first |
| Library separators | Isolated | Moderate | P2 | Consider as collections/smart-view feature |

## Evidence rule

A request does not become scope because one project exposes it. Core fit, safety, maintenance, and repeated need control priority.
