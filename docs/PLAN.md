# Agent Router Plan

## Goal

Provide one memorable front door that clarifies intent, discovers relevant
capabilities, routes to one or more specialists, synthesizes disagreement, and
asks for approval before execution.

## Phases

1. Define a capability registry and portable routing contract. **Done**
2. Build a deterministic fixture set for routing, ambiguity, consensus, and
   safety cases.
3. Implement a read-only advisor mode. **In progress**
4. Add convene mode with bounded specialist fan-out and synthesis.
5. Add thin adapters for Codex, Claude, OpenCode, OpenRouter, and project
   instruction files.
6. Run architecture, security, and adversarial prompt-injection reviews.
7. Publish installation and rollback instructions.

## Non-goals

- Replacing specialist skills.
- Automatically executing edits or external actions.
- Claiming consensus when only one specialist responded.
- Making provider-specific behavior part of the core contract.

## Acceptance gates

- Every route cites the matched capability and source.
- Low-confidence or conflicting routes ask a clarifying question.
- Execution always stops at an explicit approval gate.
- The same fixtures pass through every adapter.

## Directory contract

Each entry has a stable name, source, description, trigger vocabulary,
invocation reference, and trust level. Search has no hidden top-N cutoff;
callers choose a limit when they want one. The first backend is SQLite with
transparent lexical scoring. Future semantic search must return the same entry
shape plus evidence for its ranking.
