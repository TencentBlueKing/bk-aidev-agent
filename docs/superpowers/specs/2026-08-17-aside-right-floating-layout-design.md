# Aside Right + Floating Window Two-Phase Expand Design

**Date:** 2026-08-17  
**Status:** Approved  
**Scope:** `@blueking/ai-blueking` — apply ChatContainer right-aside layout (`c19bd0be`) in `ai-blueking.vue` and `chat-bot.vue`; rewrite floating-window expand geometry  
**Depends on:** chat-x ChatContainer aside is fixed `placement: 'right'`, no `placement` prop, fold controlled by `v-model:asideCollapsed`

## Goals

1. ChatBot / AIBlueking drop `placement`. Aside is always on the right, matching ChatContainer.
2. Floating window (`ai-blueking.vue`) expands aside to the right. Default dock is the viewport right edge, so most expands first shift the window left to vacate right space, then widen, then show aside content.
3. Fold/expand UI for the floating window lives in `AIHeader`. Embedded ChatBot does not ship a toggle; the consumer provides one.
4. `asideCollapsed` is owned by `ai-blueking.vue` in the floating-window path. ChatBot only forwards `v-model:asideCollapsed`.

## Non-Goals

- Changing ChatContainer layout, `asideCollapsed` semantics, or re-adding `placement` in chat-x.
- Embedded ChatBot providing a built-in aside toggle.
- Changing Nimbus, drag-handle, compression, or max-width-percent defaults except as they interact with aside expand clamp.
- Vue2 wrapper behavior beyond passing the new ChatBot props through existing createVue2Wrapper.

## Architecture

Geometry stays in `use-draggable`. Fold state stays in the floating-window root. ChatBot has no knowledge of the floating window.

```
AIHeader toggle-aside
        ↓
ai-blueking.vue  (owns asideCollapsed)
        ↓ expand: await expandForSidePanel(extraWidth) → then asideCollapsed = false
        ↓ collapse: asideCollapsed = true → then await collapseSidePanel()
        ↓
ChatBot  v-model:asideCollapsed  (passthrough; local fallback if unbound)
        ↓
ChatContainer  strictly controlled; aside always right
```

| Unit | Does | Does not |
|------|------|----------|
| `use-draggable` | Shift left to vacate right, widen with left edge fixed, remember collapsed/expanded layout, clamp to viewport | Know aside tabs or ChatContainer |
| `ai-blueking.vue` + `use-panel-container` | Own `asideCollapsed`, orchestrate two-phase expand/collapse, pass state to Header and ChatBot | Touch ChatContainer internals |
| `AIHeader` | Toggle button UI, emit `toggle-aside` | Change window geometry |
| `ChatBot` | Forward `v-model:asideCollapsed`; unbound → local `ref(true)` | Accept `placement` |
| `ChatContainer` | Existing right layout; internal expand only emits `update:asideCollapsed` | Change |

Internal expand (file artifact preview, `addCustomTab`) uses the same parent path: vacate space first, then set `asideCollapsed = false`. If the parent does not update the prop, ChatContainer stays collapsed (existing controlled semantics).

## Floating window geometry

Replace the current “fix right edge, grow left” `expandForSidePanel` with “fix left edge, grow right”, plus an explicit vacate-right step when docked to the right.

Default extra width: `max(560, resizeAsideWidth ?? 0)` (`SIDE_PANEL_EXTRA_WIDTH` in `use-panel-container`). Subsequent expands prefer last `expandedPosition.width` over adding 560 again.

### Expand

```
rightSpace = viewportWidth - (x + width)
shift      = max(0, extraWidth - rightSpace)   // ≈ extraWidth when docked right
x'         = max(0, x - shift)
width'     = width + extraWidth
clamp: never push x < 0; never exceed viewport; main chat area ≥ minWidth
```

Order is mandatory (do not change `x` and `width` in the same frame — that looks like the right edge moving):

1. `updatePosition(x')` — width unchanged, whole window shifts left, right gap appears.
2. After `nextTick`, `updateSize(width')` — left edge fixed, right edge grows into the gap.
3. Then `asideCollapsed = false` — aside content fills the new right pane.

If `shift === 0` (enough room on the right already), skip step 1 and only widen.

### Collapse (reverse)

1. Set `asideCollapsed = true` first (aside must not remain in a shrinking pane).
2. After `nextTick`, shrink width with left edge fixed.
3. Shift right back to remembered `collapsedPosition` (docked-right windows return to the right edge).

Keep two remembered layouts: `collapsedPosition` / `expandedPosition` (`{ x, y, width, height }` at the last stable collapsed / expanded state).

- Re-expand with no intervening drag/resize: two-phase restore of `expandedPosition` (move `x` first if needed, then `width`). Do not add 560 again.
- Re-collapse with no intervening drag/resize: hide aside, then two-phase restore of `collapsedPosition` (shrink `width` with left edge fixed, then move `x`). Do not change `x` and `width` in the same frame.
- After the user drags or resizes the window: discard the opposite snapshot. Next expand uses `width' = currentWidth + extraWidth` and current `x`; next collapse uses `newWidth = currentWidth - extraWidth` and then docks using current geometry (typically `x = viewportWidth - newWidth` when the window was right-aligned).

### Clamp / max width

- If there is not enough room to shift left, shift as far as possible and reduce aside extra width so the main area stays ≥ `minWidth`.
- Existing container `maxWidth` (default 80% viewport) still applies after expand.

## API

### AIHeader

- Place the toggle in `right-section`, immediately left of the compression icon.
- Icon: chat-x `CollapsedAsideIcon`.
- Props: `asideCollapsed: boolean` (display), `showAsideToggle: boolean` (default `true`). When `hideHeader` is true the header is not rendered, so the toggle is gone with it. Consumers that keep the header but do not want this button set `showAsideToggle=false`.
- Emit: `toggle-aside`.
- Header does not call expand/collapse APIs.

### ChatBot

- **Remove** `placement` (breaking).
- **Add** optional `asideCollapsed?: boolean` and `update:asideCollapsed`.
- Bound (floating window): strictly controlled.
- Unbound (embedded): local `ref(true)`, same fallback as ChatContainer.
- Forward `v-model:asideCollapsed` to ChatContainer.
- Keep `execution-panel-change` for collapse/width reporting. The floating root uses the width to refresh `extraWidth` only. `handleExecutionPanelChange` must **not** call `expandForSidePanel` / `collapseSidePanel`; window geometry is driven only by `asideCollapsed` / Header `toggle-aside`.

### AIBlueking / use-panel-container

- Hold `asideCollapsed` (default `true`).
- `expandForSidePanel` / `collapseSidePanel` become `async` and resolve after their geometry steps (position then size, or shrink then restore). The orchestrator awaits them instead of duplicating `nextTick`. Public proxies on `DraggableContainer` / `ComponentManager` stay; they become async too.
- Header `toggle-aside` or ChatBot `update:asideCollapsed(false)` → `await expandForSidePanel(extraWidth)`, then set `asideCollapsed = false`.
- `update:asideCollapsed(true)` → set state first, then `await collapseSidePanel()`.
- Set `isSidePanelExpanded` at the start of expand (same as today). A second expand is a no-op, including during the in-flight sequence.
- `hide()` / `handleClose` during expand: abort remaining size/position writes, keep `asideCollapsed = true`, restore `collapsedPosition` captured at sequence start.

## Error handling

| Case | Behavior |
|------|----------|
| Viewport too narrow to shift full `extraWidth` | Shift as far as possible; cut aside width; main area ≥ `minWidth` |
| Drag / resize viewport during expand | Finish the sequence with coordinates captured at start; write `expandedPosition` from geometry after it ends |
| Close panel during expand | Abort widen; keep `asideCollapsed = true`; restore position from the start of this sequence |
| Embedded ChatBot without `asideCollapsed` | Internal expand (artifacts, custom tabs) may open the aside; no floating-window geometry |

## Testing

- `use-draggable`: docked-right expand is shift-then-widen; enough right space skips shift; collapse is hide-then-shrink-then-shift-right; clamp; second click during animation ignored.
- ChatBot: no `placement` prop; controlled vs unbound `asideCollapsed`.
- AIHeader: toggle sits left of compression; emits `toggle-aside`.
- In-repo docs and `packages/ai-blueking/skills/`: remove `placement`; document right aside, Header toggle, two-phase floating expand. GitHub skills-manager-backup sync is a follow-up, not this work.

## Breaking changes

- `ChatBot.placement` removed. Call sites that pass `placement="left"` / `"right"` must delete it. Aside is always right.
- Floating window visual: aside opens on the right; the window usually moves left before growing. Previously it grew left with the right edge fixed.

## Out of scope follow-ups

- Document-site changelog / npm CHANGELOG for the release that ships this (separate `/doc-update` pass).
- Syncing skill copies to GitHub `skills-manager-backup` (in-repo `packages/ai-blueking/skills/` **is** in scope).
