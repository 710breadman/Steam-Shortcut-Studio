# UI Framework Decision

**Status:** Accepted for the next implementation phase  
**Date:** 2026-07-11

## Decision

Do not perform an immediate full migration from Tkinter to PySide6 or another GUI toolkit.

Use an incremental modernization strategy:

1. Extract domain logic and state from `ui.py`.
2. Build a reusable design-token layer.
3. Prototype the approved dark/blue shell using CustomTkinter for window chrome, cards, buttons, tabs, and theme controls.
4. Continue using ttk widgets where they are stronger, especially the current table/tree behavior, until a tested replacement exists.
5. Re-evaluate PySide6 only after the transaction, selection, queue, and persistence layers are UI-independent.

## Why This Fits the Project

The current application already works on Windows, SteamOS, and Bazzite and is intentionally standard-library-first. A complete GUI migration would combine visual work with event-loop, packaging, threading, and platform changes. That would create unnecessary risk before the Steam-write foundation is complete.

CustomTkinter is based on Tkinter, can be mixed with normal Tkinter widgets, provides modern customizable widgets, supports light/dark appearance modes, themes, and high-DPI scaling, and uses the MIT license. This makes it suitable for an incremental shell prototype without rewriting the domain core.

PySide6 remains the strongest long-term option if the project eventually needs a richer model/view table, more advanced layout behavior, or extensive custom rendering. It also brings a larger dependency, larger packaged builds, Qt-specific deployment work, and a much broader migration.

## Options Considered

### Option A — Continue with ttk only

**Advantages**

- No new runtime dependency
- Lowest packaging risk
- Existing code remains compatible

**Disadvantages**

- Harder to reach the approved mockup quality
- More custom styling work
- Rounded cards, polished controls, and consistent visual states remain difficult

**Decision:** Keep ttk where useful, but do not rely on it alone for the new shell.

### Option B — CustomTkinter shell plus ttk table

**Advantages**

- Incremental adoption
- Compatible with existing Tkinter event loop
- Modern widgets and appearance modes
- Supports custom themes and high-DPI scaling
- MIT licensed
- Can coexist with existing widgets

**Disadvantages**

- No first-class high-performance data table comparable to Qt model/view
- Mixed widget styling needs care
- Adds a runtime and packaging dependency

**Decision:** Selected for the first UI prototype.

### Option C — ttkbootstrap

**Advantages**

- Small conceptual change from ttk
- Built-in themed styles
- Existing widgets remain familiar

**Disadvantages**

- Improves theming more than structure
- Less direct support for the card-heavy, premium mockup style
- Does not solve the oversized UI module or state boundaries

**Decision:** Not selected as the primary direction. It remains a fallback if CustomTkinter packaging or mixed-widget behavior proves unsuitable.

### Option D — PySide6 / Qt Widgets

**Advantages**

- Strong model/view architecture
- Excellent tables, delegates, threading primitives, styling, and layout tools
- Mature cross-platform desktop framework
- Better fit for a very large library and complex inspector over the long term

**Disadvantages**

- Full UI rewrite
- New event model and packaging strategy
- Larger distribution size
- More licensing and deployment diligence
- Higher short-term risk while Steam writes are still being hardened

**Decision:** Defer. Reconsider after the service boundaries are complete.

## Prototype Boundary

The first visual prototype should include only:

- Application window and top bar
- Left navigation
- Theme/accent selector
- Library table container
- Empty right inspector shell
- Bulk-selection summary bar
- Safety/backup status cards using mock data

It must not write Steam files.

## Prototype Success Criteria

- Closely resembles approved mockup #2.
- Runs on Windows and Linux.
- Theme changes remain available.
- Existing table behavior can be embedded or adapted.
- The shell can receive library data through a controller interface.
- No scanning or Steam-write logic is duplicated inside widgets.
- Packaged build impact is measured before adoption.

## Reconsideration Trigger

Re-evaluate PySide6 when all of the following are true:

- Transaction service is complete.
- Selection and job state are UI-independent.
- Library persistence has stable IDs.
- The current table is proven to be a performance or usability blocker.
- A small PySide6 proof of concept demonstrates a clear advantage worth the migration cost.

## Research Sources

- CustomTkinter official documentation: https://customtkinter.tomschimansky.com/documentation/
- CustomTkinter repository and license: https://github.com/TomSchimansky/CustomTkinter
- Qt for Python official documentation: https://doc.qt.io/qtforpython-6/
- ttkbootstrap documentation: https://ttkbootstrap.readthedocs.io/en/latest/
