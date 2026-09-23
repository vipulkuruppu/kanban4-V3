# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single-file Kanban demo ("UOB IT PMO — Project Board"). All of it lives in `index.html`: CSS in `<style>`, markup, and vanilla JS in one `<script>`. There is no build step, package manager, linter or test suite.

## Running

Open `index.html` in a browser, or serve the directory (for example `python3 -m http.server`) and load it from there. Tasks are kept only in memory, so a page reload resets the board to the seeded sample data.

## Architecture (the `<script>` block)

- **One state object.** `state` holds `tasks`, `filters`, `nextId` and `ui` (`pendingDeleteId`, `moveMenuId`). Actions (`addTask`, `moveTask`, `deleteTask`) change `state` and then call `renderBoard()`. Note that `addTask` does not render; its callers do.
- **One render path.** `renderBoard()` is the only function that draws cards. It rebuilds each column's `innerHTML` from `applyFilters()` and updates the count badges, `renderSummary()` and the two donut charts (`renderDonut("project" | "priority")`). Transient card UI, such as the open move menu or the delete confirmation, is driven by `state.ui` and redrawn, not toggled in the DOM. After a re-render, `focusAfterRender(selector)` puts focus back where it belongs.
- **Event delegation.** One click handler on `#board` routes on `button[data-action]` (`move-toggle`, `move-to`, `delete-ask`, `delete-no`, `delete-yes`) and reads `data-id`. New card controls should follow this pattern rather than bind listeners per card, because cards are recreated on every render.
- **Charts.** `CHARTS` maps each chart to its value list and color tokens (`--proj-N`, `--prio-*`). A chart counts `tasksMatching(key)`, which applies every filter except its own, and dims the slices that aren't selected. Its legend rows are `button[data-chart-filter]`; a click handler on `#insights` validates the value against the whitelist and sets the filter. The chart colors passed the dataviz colorblind check; re-run it if you change them, because red and green are hard to tell apart.
- **Security headers.** A CSP meta tag in `<head>` allows connections only to FormSubmit and fonts only from Google Fonts. A new external host has to be added there.
- **Escaping.** Every user value put into card HTML must go through `escapeHtml()`.
- **Constant lists.** `STATUSES`, `PROJECTS`, `CATEGORIES` and `PRIORITIES` fill the `<select>` elements in `init()` and are the whitelists that `validateForm()` checks against. The four status columns are hard-coded in the HTML with `data-status`, `data-list` and `data-count` attributes, and the summary uses `sum-<domKey(status)>` ids. Adding a status means changing both the constant and the markup and CSS.
- **Dates.** Dates are local `YYYY-MM-DD` strings built by `toLocalISO()`; do not use `toISOString()`, which shifts to UTC. Overdue checks and due-date validation compare these strings directly.
- **Task IDs.** `formatId()` produces `UOB-ITPM-0001` and so on.

## Email notification (FormSubmit)

`FORMSUBMIT_ENDPOINT` near the top of the script is the only place the recipient address is set. On submit, the card is added to the board immediately, and then `notifyNewTask()` POSTs JSON to FormSubmit. If that fails, the user sees a warning toast and the board is unaffected. FormSubmit can return HTTP 200 with `success: "false"`, and that case is treated as a failure. A new address needs a one-time activation: the first submission sends a confirmation email instead of delivering.

## WhatsApp support widget

A floating button in the bottom-right corner (`#open-whatsapp`) opens the `#whatsapp` dialog, which lists `WHATSAPP_QUERIES`. Each query is a `https://wa.me/<WHATSAPP_NUMBER>?text=…` link that opens in a new tab. The dialog works like the other modals: it traps focus, closes on Escape, and returns focus to the button. The toast region sits above the button so the two don't overlap.

## Visit tracking

`startVisitTracking()` sends same-origin `navigator.sendBeacon` posts to `VISIT_ENDPOINT` (`/__visit`) with a random visit id and the time the tab was visible. It does nothing on `*.github.io` or `file://`. Only `python3 tools/visit_server.py` handles those posts. It serves the site, appends to `logs/visits.jsonl` (source IP, user agent, duration) and returns 404 for `logs/`, `tools/`, `.claude/` and the report folders. `python3 tools/visit_report.py` builds the escaped HTML report in `visit-reports/`, and the `visit-monitor` agent runs it. The logs and reports are gitignored because IPs are personal data.

## Conventions

- Accessibility is deliberate throughout. Keep it intact when changing the UI: ARIA labels on icon buttons, `aria-invalid` with per-field `err-<name>` messages, the modal focus trap and Escape handling, the `aria-live` toast region, and keyboard move and delete as an alternative to drag and drop.
- Colors and spacing come from CSS custom properties on `:root`; use those tokens instead of hard-coded values.
