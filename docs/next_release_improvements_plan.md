# Next Release Improvements Plan

## Purpose

This document tracks improvement ideas that are intentionally left out of the current single-release implementation plan. They need more real-world BLE samples or broader device evidence before implementation.

## Scope

- Do not implement these items in the current improvement release.
- Keep the current release focused on migration, canonical 24-bit identity, Home Assistant availability, state classes, diagnostics, UI, discovery, and the optional two-tariff total sensor.
- Revisit these items after the current release is stable on real Home Assistant installations.

## Task N1: Two-Tariff Real Sample Collection

Scope:

- Add a private fixture format for user-supplied BLE samples.
- Document how to capture samples from Home Assistant diagnostics or BLE tools.
- Keep public fixtures sanitized.
- Collect at least one reliable real two-tariff sample before expanding two-tariff parser behavior beyond the planned optional total sensor.

Acceptance criteria:

- A documented sample-capture workflow exists.
- At least one real two-tariff sample can be parsed and documented.
- Public test fixtures do not expose unnecessary personal/home details.

Dependencies:

- User hardware or reliable third-party sample.
- Current release diagnostics export.

Priority: P1 for the next improvement cycle.

## Task N2: Research Gas And Other Elehant Meters

Scope:

- Research gas and other Elehant meter BLE advertisements only when devices or reliable BLE samples are available.
- Do not claim functional support without tested samples.
- Keep the channel-based config model generic enough for future volume meters.
- Document confirmed packet prefixes, units, and measurement semantics separately from assumptions.

Acceptance criteria:

- README does not claim untested support.
- Research notes are documented.
- Any future implementation has real samples or a clearly reliable source.

Dependencies:

- Samples/devices for non-water Elehant meters.

Priority: P2 for the next improvement cycle.

## Task N3: Discovery Candidate Freshness UX Decision

Context:

- The current implementation filters the candidate list to recently seen unknown packets.
- After a user selects a discovery candidate, the add form keeps using the selected meter ID even if the packet is no longer recent by the time the form is submitted.
- This is intentional for the current release: selecting a candidate is treated as user intent, and rejecting the form later would be surprising. The worst practical outcome is adding a configured meter that may not currently be transmitting in the environment.

Decision fork for a future release:

- Option A: keep the current behavior. Freshness is checked only when building the discovery candidate list.
- Option B: re-check freshness on submit and abort or show an error if the selected candidate expired.
- Option C: keep submit allowed, but show candidate age/last seen in the add form so the user can make an informed choice.

Current preference:

- Keep Option A for now.
- Revisit Option C if diagnostics or UI feedback show that users need more confidence before adding discovered meters.

Acceptance criteria:

- The chosen behavior is documented in README or UI text if it changes.
- Tests cover the selected submit-time behavior.
- If candidate age is shown, it uses human-readable relative timing and does not block adding the meter.

Priority: P3 for the next improvement cycle.

## Task N4: Remove Temporary Manual YAML Import Entry Point

Context:

- The current release intentionally keeps two YAML import entry points while automatic YAML conversion is being stabilized:
  - integration-level setup captures and imports legacy YAML;
  - legacy sensor platform setup can also trigger import.
- This was useful during debugging, but it should not remain a long-term architecture.

Scope:

- After the current release is stable, remove the temporary manual/platform-triggered import path.
- Keep only the minimal import path required by Home Assistant to migrate legacy YAML safely.
- Preserve user-facing migration behavior for one release window if HA still calls the legacy platform setup.
- Remove or simplify any options UI affordance that exists only to recover from failed automatic import, if it is no longer needed.

Acceptance criteria:

- There is only one authoritative YAML migration path.
- Existing migrated config entries keep loading.
- A legacy YAML block still gets a clear migration path or a clear deprecation message.
- Tests cover the remaining import path and confirm duplicate imports cannot create duplicate entries.

Priority: P1 for the next improvement cycle.
