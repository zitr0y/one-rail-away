# Rome City Group Design Document

**Date:** 2026-07-16

## Goal
Add a "Roma" city group to `cities.toml` that maps to the key Rome stations, ensuring that unmatched member names warn but do not fail the build.

## Approach
1. Add the "Roma" city group entry to `cities.toml` mapping to:
   - `ROMA TERMINI`
   - `ROMA TIBURTINA`
   - `ROMA OSTIENSE`
   - `Roma, Stazione di Roma Tiburtina`
2. Add a comment detailing:
   - `Roma, Stazione di Roma Tiburtina` is an unmerged ÖBB duplicate of `ROMA TIBURTINA` (backlog AP) included so the union covers it.
   - The all-caps names come from the Trenitalia NeTEx feed (verified live 2026-07-16).
3. Confirm that the cities loader warn-and-skips unmatched names without failing. Add a unit test verifying this behavior for the Rome city group.

## Validation
- Run unit test for Roma city group resolver.
- Ensure all other unit tests pass.
