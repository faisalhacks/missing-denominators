# missing-denominators

Companion code for the audit of AI incident disclosure rates. Published rates
from different labs are reported in incompatible units, and most omit the
denominator needed to turn a count into a rate, so they cannot be compared as
published. This tool converts each disclosure to a common per-run unit and labels
exactly why any figure cannot be placed on that scale.

## Run

```
python convert.py
```

Python 3.8+, standard library only. No dependencies, no network, deterministic
output. Prints two tables and a provenance appendix. `python convert.py --out-dir out`
also writes them to `out/`.

## What it produces

- **Table A** — reason-coded poolability. A per-run rate is *poolable* only if it
  can be obtained, as machine-readable text, on the shared containment-breach
  estimand. Of three hand-verified disclosures, one is poolable
  (Anthropic, 4.26×10⁻⁵ = 6 / 141,006, across 3 incidents, and a
  detection-limited lower bound); the others are labelled `no-denominator`
  (OpenAI) and `different-estimand` (AISI).
- **Table B** — recoverability checklist: 16 of 21 numeric cells are not
  recoverable from public sources across the three verified disclosures.

## Three states, enforced

Every numeric field carries one state and its provenance:

- `recoverable` — published; the record cites the source.
- `derivable` — computable from published figures; the tool prints the arithmetic.
- `not_recoverable` — genuinely absent.

The schema makes fabrication a hard error: a `not_recoverable` field carrying a
number is rejected on load. The tool never estimates or interpolates.

## Files

```
convert.py         loads records, derives rates, prints Table A + Table B
schema.json        record format (JSON Schema); enforces the three states
incidents/*.json   one hand-verified record per disclosure
                   (german_wiki_incident is a visible PENDING stub;
                    _TEMPLATE.json is a blank to copy)
```

## Scope

This repository is the analysis and data only. The execution harness for the
pre-registered follow-up experiment is withheld pending a disclosure review and
is not part of this repository.

## Licence

MIT. See `LICENSE`.
