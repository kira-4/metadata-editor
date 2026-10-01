---
target: queue, library, settings after final polish
total_score: 29
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
timestamp: 2026-10-01T07-29-34Z
slug: app-static-index-html
---
# Critique: queue, library and settings at 390/1280 after the final polish pass

Method: dual-agent (A: design review · B: detector + browser)

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | The header now shows the ready count («2 من 4 جاهزة»); no progress while a session runs |
| 2 | Match System / Real World | 3 | Domain terms right; the numbered pipeline steps in Settings are unexplained |
| 3 | User Control and Freedom | 3 | Trash plus two-tap delete; no undo after a confirm |
| 4 | Consistency and Standards | 3 | «تعديل» is a small outline tag on cards and a full button in the library |
| 5 | Error Prevention | 3 | Confirm-all moves up to 50 files with a single tap |
| 6 | Recognition Rather Than Recall | 3 | Collapsed cards don't mark which values the model inferred |
| 7 | Flexibility and Efficiency | 3 | Genre memory and next-card focus exist; no shortcuts, no apply-to-rest, no Telegram deep link |
| 8 | Aesthetic and Minimalist Design | 3 | A needs-review card is about 1000px tall on a phone |
| 9 | Error Recovery | 3 | A waiting confirm leads to the missing field; failed moves offer a retry |
| 10 | Help and Documentation | 2 | No help beyond inline hints |
| **Total** | | **29/40** | **Good** (was 28) |

Corrections to A, checked against the source: Settings labels are Arabic with a Latin hint; delete takes two taps and goes to the trash; retry states exist; the shelf label is the folder/file path by design; the ready bar shows its count beside the button.
Detector: CLI 0 findings. Overlays: gray-on-colour, AI-palette and hairline-shadow findings are known false positives, inflated by hidden SPA routes. One "overflow" (the ellipsised file name, intended) and one "occluded" (the nav badge on the tab corner, minor). The diagnostics checkbox is 15×20 inside its label.

## Priority Issues
- [P2] Confirm-all moves everything with one tap: arm it with a second tap that names the count. (/impeccable harden)
- [P2] Needs-review cards are long: fold groups that are already done (green ✓). (/impeccable distill)
- [P2] Throughput: deep-link from the Telegram ping, apply genre/folder to the rest of the channel. (/impeccable shape)
- [P3] Bigger «تعديل» target placed in the thumb zone; style the debug checkbox as a switch; explain the pipeline steps. (/impeccable polish)
