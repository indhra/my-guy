# Agent Router

Personal routing layer for Codex, Claude, OpenCode, OpenRouter, ECC, GStack,
Matt Pocock skills, project instructions, and other agent capabilities.

## Status

Research and architecture phase. The router will clarify vague requests,
discover relevant capabilities, convene specialists when useful, synthesize
their findings, and require approval before consequential actions.

## Design rule

The core must remain harness-neutral. Each host gets a thin adapter; routing
behavior and evaluation fixtures remain shared.
