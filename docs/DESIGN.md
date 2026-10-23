# Design notes

This app is a Tk application that has to read as a Google product. The constraint is real: Tk cannot blur, cast shadows, antialias arbitrary shapes, or expose an accessibility tree. The response is not to fake those things badly, but to map Material 3 onto what Tk does well.

## Token source

Material 3 role palette seeded on Google Blue `#0B57D0` (production Google), cross-checked against the reference M3 dark scheme (`#ADC7FF` primary). Ratios were computed from the hex values, not eyeballed:

| Pair | Light | Dark |
|---|---:|---:|
| body on surface | 16.4:1 | 14.4:1 |
| body on card | 14.8:1 | 12.8:1 |
| secondary on surface | 8.9:1 | 10.9:1 |
| filled button label | 6.4:1 | 7.8:1 |
| focus ring on surface | 6.1:1 | 11.0:1 |
| field border (`outline`) | 4.1:1 | 5.4:1 |

## What maps cleanly

- **Colour roles**: 1:1.
- **Type scale**: 12–32 px. Families resolve in order Google Sans → Product Sans → Roboto →
  Noto Sans → Liberation Sans, checking `font.families` before use. An unknown family on X11
  silently becomes `fixed` at 10 px; `pick_family` exists so that never happens.
- **Tabs**: selected tab uses `surface-high` plus `primary` text, because a 3 px M3 indicator
  cannot be attached to a ttk tab without drawing a custom element.
- **State layers**: hover 8%, press 12%, precomputed blends animated at 16 ms ticks over ~120 ms.
- **Shape**: pills are drawn with real arcs; cards are outlined (M3's own outlined-card variant).
- **Density**: 30 px rows, 8 px spacing grid, 32 px targets.

## What is deliberately dropped

- **Elevation**: no shadows. M3 2025 spec already replaces tint with surface steps plus a 1 px outline; that is exactly what the cards do.
- **Ripples**: a 250 ms ripple on every click reads as decoration, not feedback, and Tk cannot clip it to rounded shapes.
- **A dimmed scrim behind the palette**: Tk has no alpha; a stipple reads as 1995, so the overlay relies on a distinct surface and a 1 px outline instead.
- **Blur / vibrancy**: impossible without compositing; a grey rectangle imitating glass is worse than an opaque surface.
- **Scroll-linked effects, springs, shared-element transitions**: wrong tool, wrong medium, and they fight keyboard use.

## Long work: Install and background tasks

Installing source, creating a venv and using pip are too slow for the Tk thread.
They run through `App.start_task`, which gives the view a thread-safe
`report(phase, done, total, detail)` callback and a cancellation event. Progress
events cross the same queue as process output and are drained on the main loop,
so no worker ever touches a widget. The Install screen maps phases onto one
determinate 8 px bar, keeps the exact phase and detail visible, and writes a
human log line at each 10 % bucket instead of 107 file-by-file lines. Cancelling
keeps `.part` files, so retry resumes rather than restarts.

The Guide is the other half of that decision: a long-running task is only honest
if the user can find out what it is doing and what to do when it fails. Each
Guide topic names the screen, the steps and the exact recovery for the errors
the CLIs actually emit. The header Guide button opens the topic for the screen
you were reading, so help is contextual rather than a separate manual.

## Interaction rules

1. Pointer feedback only, ≤150 ms, never twice in a row on the same element.
2. Every action has a keyboard path; the palette (`Ctrl+K`) is the discovery surface.
3. Focus is a 2 px ring drawn outside the fill, in `on-surface`, so it contrasts with both the button and its parent.
4. Destructive process actions confirm; stops escalate SIGTERM → SIGKILL after 3 s.
5. Failure is persistent in the console (`[exit N]`), transient in the snackbar; both are reachable without a mouse. Install failures also stay in the activity card with the phase and detail, not only in a toast.
6. Empty states name the reason and offer the next action (e.g. Runs → "Run demo", Setup → "Open Install").
7. Text areas never trap `Tab`; `Shift+Tab` returns to the form.
8. UI scale is a first-class setting (`Ctrl+=`), because negative Tk font sizes are pixels and ignore OS DPI.

## References

- Material 3 colour roles and state layers — `material-components/material-web`, `material-foundation/material-color-utilities`.
- Dense professional tables (24/32/40 px rows), empty/loading copy — IBM Carbon.
- Focus visibility and 24 px targets — WCAG 2.2 SC 2.4.11, 2.5.8.
- Headerbar/sidebar split and per-app dark preference — GNOME libadwaita.
- ttk styling that survives real state maps — `rdbende/Sun-Valley-ttk-theme`, `israel-dryer/ttkbootstrap`.
