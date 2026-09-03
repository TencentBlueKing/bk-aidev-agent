# AiSkillList Skill 列表

> 能力域：输入交互 ｜ 导入：`import { AiSkillList } from '@blueking/chat-x'` ｜ since 1.0.0

/ Skill 选择列表，供 AiSlashInput 插入 Skill 标签。 无 icon 或 icon 加载失败时展示 skill_name 首字母 fallback。 源码位置：src/components/chat-input/ai-slash-input/ai-skill-list/ai-skill-list.vue。

**关联**：ai-slash-input（输入 / 时由 AiSlashInput tippy 菜单渲染）、chat-input（经 ChatInput.skills 透传数据源）

---

# AiSkillList Skill 列表

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/ai-slash-input/ai-skill-list/ai-skill-list.vue`
- **能力说明**：`/` Skill 选择列表，供 `AiSlashInput` 插入 Skill 标签；列表项固定高度且 `flex-shrink: 0`，避免滚动容器内被压缩。

## 行为说明

- 仅展示 `skill_name`，不展示 `description`
- 支持键盘上下选择与 Enter 确认（`useMenuKeydown`）；`skills` 变化时高亮重置到首项
- 点击列表项调用 `onSelect(skill)`
- 图标规则：
  - 有 `icon` 且未加载失败：渲染 `<img>`
  - 无 `icon`，或 `<img>` 触发 `@error`：渲染首字母 fallback（`skill_name[0]` 大写，蓝底白字）

## API 摘要

### Props

| 属性名   | 类型                               | 必填 | 说明                         |
| -------- | ---------------------------------- | ---- | ---------------------------- |
| skills   | `ISkillListItem[]`                 | ✅   | Skill 列表数据               |
| onSelect | `(skill: ISkillListItem) => void`  | ✅   | 选中 Skill 时的回调          |

### Emits

- 无（选择通过 `onSelect` prop 回调）。

### Slots

- 无。

### Expose

- 无。

## 类型定义

```typescript
interface ISkillListItem {
  description: string;
  icon: string;
  skill_code: string;
  skill_name: string;
}
```

## 组件依赖

- `useMenuKeydown`（键盘导航）

## 关联组件

- [AiSlashInput](/components/input/ai-slash-input) — 输入 `/` 时渲染本列表
- [ChatInput](/components/input/chat-input) — 通过 `skills` prop 透传数据

## 使用建议

- 优先通过 `ChatInput` / `AiSlashInput` 使用；直接使用前确认 `skills` 结构符合 `ISkillListItem`。
- 上层应对已插入的 Skill 做去重过滤（`AiSlashInput` 已实现）。
