# SIGNAL_UPDATE_V1 Design

Mode: shadow/dev only.

## Objective
Detect valid candidates blocked by `duplicate_signal_suppressed` or by active same symbol+direction lifecycle gates and classify whether they are useful updates to an already active signal.

## Non-goals
- No public Telegram publication.
- No duplicate signal creation.
- No strategy/filter changes.
- No paper/live execution changes.

## Detection
A candidate is observed only when it remains `VALID` but is blocked by one of:
- `duplicate_signal_suppressed`
- `active_same_symbol_direction_without_reentry`
- `max_reentries_reached`

The active reference is the latest published signal with the same `symbol` and `direction`.

## Classification
- `STRENGTHENED_SIGNAL`: current score is not lower than active score, or RR improves.
- `REENTRY_CANDIDATE`: new dedupe snapshot/candle plus existing reentry confirmation logic.
- `INVALIDATION_WARNING`: context worsens through failed RR, choppy/ranging context, harmful warnings, or failed quality/confluence filters.
- `NO_UPDATE`: duplicate remains informationally redundant.

## Runtime events
- `signal_update_v1_detected`
- `signal_update_v1_classified`
- `signal_update_v1_shadow_decision`

## Safety
The update always returns `public_allowed=false` and never changes the existing publishability branch. DEV notification is optional behind `SIGNAL_UPDATE_V1_DEV_NOTE_ENABLED=false` by default.
