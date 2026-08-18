# Aside Right + Floating Window Two-Phase Expand Implementation Plan

> **For agentic workers:** Implement in this session. Do **not** commit per task — the user will review the complete feature. Spec: `docs/superpowers/specs/2026-08-17-aside-right-floating-layout-design.md`

**Goal:** ChatBot/AIBlueking drop `placement` (aside always right); floating window vacates right space then widens before showing aside; Header owns the toggle.

**Architecture:** Geometry stays in `useDraggable` (`expandForSidePanel` / `collapseSidePanel` become async two-phase). `ai-blueking.vue` owns `asideCollapsed` via `usePanelContainer`. ChatBot only forwards `v-model:asideCollapsed`. ChatContainer is unchanged.

**Tech Stack:** Vue 3 + TypeScript, Vitest + Vue Test Utils, `@blueking/chat-x` (`CollapsedAsideIcon`, `ChatContainer`)

## Global Constraints

- Do not change chat-x ChatContainer layout or `asideCollapsed` semantics.
- Do not re-add `placement` on ChatBot / ChatContainer.
- Embedded ChatBot does not ship an aside toggle.
- `execution-panel-change` must not call expand/collapse; it only refreshes `extraWidth`.
- `expandForSidePanel` / `collapseSidePanel` must not change `x` and `width` in the same frame.
- `maxWidthPercent` stays 80 on the floating container (already passed from `ai-blueking.vue`).
- No per-task git commits.

## File map

| File | Responsibility |
|------|----------------|
| `src/frontend/ai-blueking/packages/ai-blueking/src/containers/use-draggable.ts` | Two-phase shift-then-widen / shrink-then-shift; abort; snapshot invalidation |
| `src/frontend/ai-blueking/packages/ai-blueking/src/containers/types.ts` | Async + `abortSidePanelSequence` on expose/return types |
| `src/frontend/ai-blueking/packages/ai-blueking/src/containers/draggable-container.vue` | Expose abort |
| `src/frontend/ai-blueking/packages/ai-blueking/src/manager/types.ts` | `ContainerController` async signatures |
| `src/frontend/ai-blueking/packages/ai-blueking/src/manager/component-manager.ts` | Proxy async + abort |
| `src/frontend/ai-blueking/packages/ai-blueking/src/composables/use-panel-container.ts` | Own `asideCollapsed`, orchestrate two-phase, stop driving geometry from `execution-panel-change` |
| `src/frontend/ai-blueking/packages/ai-blueking/src/ai-blueking.vue` | Wire Header toggle + `v-model:asideCollapsed` |
| `src/frontend/ai-blueking/packages/ai-blueking/src/components/chat-bot.vue` | Remove `placement`; controlled/uncontrolled `asideCollapsed` |
| `src/frontend/ai-blueking/packages/ai-blueking/src/components/types.ts` | Props/emits |
| `src/frontend/ai-blueking/packages/ai-blueking/src/components/ai-header/*` | Toggle UI left of compression |
| `src/frontend/ai-blueking/packages/ai-blueking/src/vue2.ts` | `update:asideCollapsed` emit name |
| `src/frontend/ai-blueking/packages/ai-blueking/src/lang/index.ts` | 展开侧栏 / 收起侧栏 |
| Playground + `packages/ai-blueking/skills/` | Drop `placement`; document right aside + Header toggle |

---

### Task 1: `useDraggable` two-phase geometry

**Files:**
- Create: `src/frontend/ai-blueking/packages/ai-blueking/src/containers/__tests__/use-draggable.spec.ts`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/containers/use-draggable.ts`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/containers/types.ts`

**Interfaces:**
- Produces: `expandForSidePanel(extraWidth: number): Promise<void>`
- Produces: `collapseSidePanel(): Promise<void>`
- Produces: `abortSidePanelSequence(): void`

- [ ] **Step 1: Write failing tests**

Mount `useDraggable` inside a tiny component so `nextTick` / lifecycle work. Stub `window.innerWidth = 1920`. Default dock: `defaultLeft = 1520`, `initWidth = 400`.

Cases:
1. Docked-right expand: after await, `left === 960`, `width === 960`. Watch `left`/`width`: first mutation is left-only, second is width-only.
2. Enough right space (`defaultLeft = 100`): skip shift; `left` stays 100, `width === 960`.
3. Collapse reverse: hide flag already handled by caller; this function shrinks width first then restores `x`. After await, back to `{ x: 1520, width: 400 }`.
4. Clamp: `innerWidth = 800`, extra 560 → `left === 0`, `width === 800` (cut aside; main stays 400).
5. Second `expandForSidePanel` while expanded / in-flight: no-op (width unchanged).
6. `abortSidePanelSequence` during expand: restore start position, `isSidePanelExpanded === false`.
7. Drag while collapsed nulls `expandedPosition` so next expand uses `currentWidth + extraWidth`.

- [ ] **Step 2: Implement geometry**

Keep `collapsedPosition` / `expandedPosition`. Add `sequenceId`, `lastExtraWidth`, `wasRightDocked`.

Expand:
```
if (isSidePanelExpanded) return
collapsedPosition = current
isSidePanelExpanded = true
id = ++sequenceId
targetWidth = expandedPosition?.width ?? current.width + extraWidth
targetWidth = min(targetWidth, maxWidth, viewportWidth)
targetWidth = max(targetWidth, minWidth)
needed = targetWidth - current.width
rightSpace = viewportWidth - (current.x + current.width)
shift = max(0, needed - rightSpace)
x' = max(0, current.x - shift)
targetWidth = min(targetWidth, viewportWidth - x')
lastExtraWidth = targetWidth - current.width
wasRightDocked = abs(current.x + current.width - viewportWidth) < 1
updatePosition(x', y)
await nextTick()
if (id !== sequenceId) return
updateSize(targetWidth, height)
await nextTick()
expandedPosition = getPositionAndSize()
```

Collapse:
```
if (!isSidePanelExpanded) return
expandedPosition = current
isSidePanelExpanded = false
id = ++sequenceId
targetWidth = collapsedPosition?.width ?? max(minWidth, current.width - lastExtraWidth)
targetX = collapsedPosition?.x ?? (wasRightDocked ? viewportWidth - targetWidth : current.x)
updateSize(targetWidth, height)
await nextTick()
if (id !== sequenceId) return
updatePosition(targetX, y)
```

Abort: `sequenceId++`; if a snapshot exists, restore `collapsedPosition` (position+size allowed together — panel is hiding); `isSidePanelExpanded = false`.

Drag/resize stop: if expanded, `expandedPosition = current` and `collapsedPosition = null`; if collapsed, `expandedPosition = null`.

- [ ] **Step 3: Run** `pnpm --filter @blueking/ai-blueking test src/containers/__tests__/use-draggable.spec.ts`

---

### Task 2: Container / manager async proxies

**Files:**
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/containers/types.ts` (`DraggableContainerExpose`, `UseDraggableReturn`)
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/containers/draggable-container.vue` (expose `abortSidePanelSequence`)
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/manager/types.ts` (`ContainerController`)
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/manager/component-manager.ts`

Signatures:
```
expandForSidePanel(extraWidth: number): Promise<void>
collapseSidePanel(): Promise<void>
abortSidePanelSequence(): void
```

Manager methods `return this.containerRef?.expandForSidePanel?.(extraWidth) ?? Promise.resolve()` (same for collapse). `abortSidePanelSequence` no-ops if no ref.

---

### Task 3: ChatBot `placement` removal + `asideCollapsed`

**Files:**
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/components/types.ts`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/components/chat-bot.vue`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/vue2.ts` (`chatBotEmitNames` add `'update:asideCollapsed'`)
- Create: `src/frontend/ai-blueking/packages/ai-blueking/src/components/__tests__/chat-bot-aside.spec.ts` (same ChatContainer stub pattern as `chat-bot-side-render.spec.ts`)

- Remove `placement` from `ChatBotProps` and `withDefaults`.
- Add `asideCollapsed?: boolean` (no default in `withDefaults` — `undefined` means unbound).
- Add emit `'update:asideCollapsed': [collapsed: boolean]`.
- Local fallback + computed, same as ChatContainer:

```ts
const localAsideCollapsed = ref(true);
const asideCollapsed = computed({
  get: () => props.asideCollapsed ?? localAsideCollapsed.value,
  set: (collapsed: boolean) => {
    if (props.asideCollapsed === undefined) localAsideCollapsed.value = collapsed;
    emit('update:asideCollapsed', collapsed);
  },
});
```

- Template: drop `:placement`; add `v-model:aside-collapsed="asideCollapsed"`.
- Keep `@collapse-change="handleExecutionPanelChange"` (width reporting only).

Tests: stub does not receive `placement`; unbound → ChatContainer gets `asideCollapsed === true`; bound `false` is forwarded; `wrapper.setProps({ asideCollapsed: false })` updates the stub.

---

### Task 4: AIHeader toggle

**Files:**
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/components/ai-header/types.ts`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/components/ai-header/index.vue`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/lang/index.ts`

Props: `asideCollapsed?: boolean` (default `true`), `showAsideToggle?: boolean` (default `true`).
Emit: `'toggle-aside': []`.

Place a clickable span **immediately left of** the compression icon. Icon: `CollapsedAsideIcon` from `@blueking/chat-x`. Tooltip: `t('展开侧栏')` / `t('收起侧栏')`. `@click.stop` so drag-handle does not swallow it.

Add `展开侧栏: 'Expand side panel'` and `收起侧栏: 'Collapse side panel'` to `langData`. Add `恢复默认尺寸: 'Restore default size'` only if missing (header already uses that key).

Create `src/frontend/ai-blueking/packages/ai-blueking/src/components/ai-header/__tests__/ai-header-aside-toggle.spec.ts`: stub `bkui-vue` / `vue-tippy` / `use-history-dropdown` as needed; assert toggle exists left of compression class `bkai-yasuo` / `bkai-morenchicun`; click emits `toggle-aside`; `showAsideToggle=false` hides it.

---

### Task 5: Orchestration in `usePanelContainer` + `ai-blueking.vue`

**Files:**
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/composables/use-panel-container.ts`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/composables/__tests__/use-panel-container.spec.ts`
- Modify: `src/frontend/ai-blueking/packages/ai-blueking/src/ai-blueking.vue`

Hold:
```
asideCollapsed = ref(true)
extraWidth = SIDE_PANEL_EXTRA_WIDTH
```

```ts
const handleExecutionPanelChange = (_isCollapse: boolean, resizeAsideWidth?: number) => {
  extraWidth = Math.max(SIDE_PANEL_EXTRA_WIDTH, resizeAsideWidth ?? extraWidth);
};

const expandAside = async () => {
  if (!asideCollapsed.value) return;
  await componentManager.expandForSidePanel(extraWidth);
  asideCollapsed.value = false;
};

const collapseAside = async () => {
  if (asideCollapsed.value) return;
  asideCollapsed.value = true;
  await nextTick();
  await componentManager.collapseSidePanel();
};

const handleToggleAside = async () => {
  if (asideCollapsed.value) await expandAside();
  else await collapseAside();
};

const handleAsideCollapsedUpdate = async (collapsed: boolean) => {
  if (collapsed === asideCollapsed.value) return;
  if (collapsed) await collapseAside();
  else await expandAside();
};

const hide = () => {
  asideCollapsed.value = true;
  componentManager.abortSidePanelSequence();
  componentManager.hidePanel();
};
```

Return `asideCollapsed`, `handleToggleAside`, `handleAsideCollapsedUpdate`, `handleExecutionPanelChange`.

`ai-blueking.vue`:
- `AIHeader`: `:aside-collapsed="asideCollapsed"`, `@toggle-aside="handleToggleAside"`
- `ChatBot`: `v-model:aside-collapsed="asideCollapsed"` **cannot** be a raw ref write — ChatBot emit must go through `handleAsideCollapsedUpdate` so geometry runs first:

```vue
:aside-collapsed="asideCollapsed"
@update:aside-collapsed="handleAsideCollapsedUpdate"
```

Do **not** use `v-model:aside-collapsed` on ChatBot (that would set the ref before expand). Keep `@execution-panel-change="handleExecutionPanelChange"`.

Tests: `handleExecutionPanelChange(false, 600)` does not call `expandForSidePanel`; `handleToggleAside` from collapsed awaits expand then `asideCollapsed === false`; `handleAsideCollapsedUpdate(true)` sets true then collapse; `hide` calls `abortSidePanelSequence`. Mock manager must include `abortSidePanelSequence` and async expand/collapse.

---

### Task 6: Call sites + skills

**Files:**
- `playground/components/side-render/FlowAgentSideRenderDemo.vue` — delete `placement="left"`
- `playground/components/side-render/side-render-code-examples.ts` — delete `placement="left"`
- `skills/ai-blueking-dev/references/chatbot-api.md` — drop `placement` row; add `asideCollapsed` + `update:asideCollapsed`; note aside is always right; floating window toggle is Header
- `skills/ai-blueking-dev/references/chat-x-api.md` — ChatContainerProps: remove `placement?`; document `asideCollapsed` strictly controlled, aside always right
- `skills/ai-blueking-dev/references/integration-patterns.md` — remove `placement="right"` example; document `v-model:asideCollapsed` for embedded ChatBot; floating window uses Header

Do not edit VitePress / npm CHANGELOG (spec follow-up).

---

### Task 7: Verify

Run: `pnpm --filter @blueking/ai-blueking test`

Expected: all packages/ai-blueking tests pass, including new specs.

Manual (playground `pnpm --filter @blueking/ai-blueking dev`): floating window docked right → Header toggle shifts left, then widens, then aside appears on the right; collapse reverses; embedded ChatBot still has no built-in toggle.
