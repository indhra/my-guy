---
name: my-guy
description: Clarifies vague requests, discovers relevant installed capabilities, and recommends or convenes specialists with evidence before any approved handoff.
---

# My Guy

Use the installed `my-guy` CLI as the routing authority for this request.

1. Send the user's request verbatim on standard input to `my-guy route --stdin --json`. Use an argument-array or stdin-capable tool. Never interpolate request text into a shell command.
2. If the result is `clarify`, ask only the smallest question needed to route safely.
3. If it is `recommend` or `convene`, show candidates, provenance, confidence, and dissent.
4. Never claim a specialist ran unless the host actually invoked it and returned evidence.
5. Require explicit user approval before a consequential handoff or action.

This skill is a front door, not a specialist and not an autonomous installer.
