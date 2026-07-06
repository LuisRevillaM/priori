# The Film Room — design charter (ratified by the owner, 2026-07-05)

The mockup at `film-room-mockup.html` is the ratified reference.
Open it in a browser; it is the spec for look, layout, and motion.

## The four laws

1. **The film is the interface.** The 2D pitch replay is the hero —
   every answer is something you can watch: real tracking frames,
   evidence drawn on the turf (carry trails, pressure rings, stage
   labels), scrubber with frame/clock readout.
2. **Every number is a door.** Rate → its moments → a moment's replay
   with the measurement overlaid. No dead-end numbers.
3. **Unknown is never hidden.** Every aggregate renders observed +
   bounds + unknown share (the amber/slate partition strip). UNKNOWN
   moments appear in slate with their truncation reason. The interval
   is the brand.
4. **Refusals are answers.** A refusal renders the named missing
   capability and, when possible, the nearest measurable question as
   a one-click alternative. Clarifications render as choosable
   readings; the answer resumes the compile.

## Tokens

Ink #0B0F0D · panel #111814 · turf #1E3A2A · turf-line #3A5C46 ·
chalk #E8F2EA · chalk-dim #9FB3A6 · amber #FFB13D (accent + observed)
· amber-dim #8A6524 (interval range) · slate #8B93A0 (UNKNOWN only) ·
fail #6E4A45 · home #5FB0FF · away #FF6E5E · ball #F5F0E6.
Monospace for numbers, hashes, clocks (tabular-nums); system sans for
prose. Sharp corners (3-6px), hairline #1C2620 borders, no shadows.

## Non-negotiables

- Provenance-true rendering: the replay draws REAL canonical tracking
  frames for the moment's window; overlays derive from the actual
  evidence rows (witness frames, ids, statuses). A demo pixel that is
  not what its caption says is a defect equal to a wrong answer.
- Never show a cold query: flagship questions pre-warm at startup.
- The provenance strip (plan hash, tree) is always visible.
