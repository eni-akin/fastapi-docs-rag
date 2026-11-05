# Triage labels

Use these strings in an implementation issue's `Status:` field.

| Canonical role | Local value | Meaning |
|---|---|---|
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate the issue |
| `needs-info` | `needs-info` | Waiting for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified and ready for agent implementation |
| `ready-for-human` | `ready-for-human` | Requires human implementation |
| `wontfix` | `wontfix` | Will not be actioned |

Record implementation completion separately with `Resolution: done` and a brief verification note; completion is not a sixth triage role.
