# Element v6 data layer

Element v6 keeps product configuration separate from FM27 memory mappings. The files in this folder are Element-owned JSON definitions and are shipped beside the Windows executable as `element-data/`.

At runtime Element first checks for an external JSON file beside the executable. If it is absent or invalid, the build falls back to the embedded copy compiled into the executable. This lets us update presets, ratings, role profiles and capability labels without changing memory-write code.

## Files

- `capabilities.json` — read/write support and certification state for each feature.
- `presets.json` — data-driven actions. Every action declares a mapping/capability requirement; unavailable actions remain gated rather than guessing memory writes.
- `ratings.json` — Element team-selection and role-scoring weights.
- `tactics.json` — neutral formation/position definitions used by tactical tooling.

## Confidence levels

`unknown -> candidate -> semantic-only -> witnessed -> cross-witnessed -> certified-read -> certified`

A JSON capability can describe a feature, but it never grants write permission by itself. Native writes still require a certified FM27 record chain in code.

## Third-party reference policy

The v6 architecture was informed by observable product behavior and user-provided configuration examples. Element does not redistribute FMRTE binaries, graphics, localization files, or proprietary implementation code. The JSON schema and implementation here are independent Element formats.
