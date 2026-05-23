# CMM-1740 Protocol Vocabulary Evolution

## Problem

Earlier public material mentions `promote`, `phase.complete`, `backlog`, and
`ready`. The core v0.4.1 state machine uses `todo`, `in_progress`, `review`,
`done` and the actions `claim`, `complete`, `review`, `issue.report`.

## Position

The older terms are historical or profile-specific. They are not additional
canonical actions in v0.4.1.

## Mapping

| Term | Profile | Status | v0.4.1 mapping |
| --- | --- | --- | --- |
| `promote` | paper v0.3 | historical | `claim` |
| `phase.complete` | paper v0.3 | historical | `complete` |
| `backlog` | paper v0.3 / clinic-asr | historical/profile-specific | `todo` |
| `ready` | paper v0.3 / clinic-asr | historical/profile-specific | `todo` |
| `claim` | core v0.4.1 | canonical | unchanged |
| `complete` | core v0.4.1 | canonical | unchanged |
| `done` | core v0.4.1 | canonical | immutable terminal state |

## Recommendation

Future papers and READMEs should describe old vocabulary as evolution history or
as an alternate profile, never as the active core state machine.

