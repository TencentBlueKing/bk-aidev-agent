# FileIcon 文件类型图标

> 能力域：辅助能力 ｜ 导入：`import { FileIcon } from '@blueking/chat-x'` ｜ since 1.0.0

按扩展名渲染文件类型图标：内联 svg，尺寸用 1em 跟随外层 font-size； 扩展名解析走 normalizeFileExtension（优先 fileType，缺省回退 fileName，大小写不敏感， 支持 Dockerfile / .gitignore 这类无扩展名或点号开头的文件）；未登记类型返回 unknown 兜底图标。 源码位置：src/components/file-icon/file-icon.vue，图标注册表在 src/icons/file-icons.ts。

**关联**：file-artifact-panel（文件产物列表与预览头使用该组件展示类型图标）、assistant-message（消息内的文件产物卡片使用该组件）

---

# FileIcon 文件类型图标

> **能力域**：辅助能力

`FileIcon` 按文件扩展名渲染对应的类型图标，用于文件列表、附件卡片、产物预览头等需要「一眼看出这是什么文件」的场景。图标以内联 svg 形式打进包内，不产生额外网络请求，也不需要消费方配置静态资源路径。

## 源码事实

- **源码位置**：`src/components/file-icon/file-icon.vue`
- **图标注册表**：`src/icons/file-icons.ts`（导出 `getFileIconSvg` / `UNKNOWN_FILE_ICON_SVG`）
- **扩展名解析**：`src/utils/file-type.ts` 的 `normalizeFileExtension`

## 核心能力

- **扩展名驱动**：优先取 `fileType`，缺省时回退 `fileName` 推断；大小写不敏感
- **特殊文件名**：`Dockerfile` / `Makefile` 这类无扩展名文件，以及 `.gitignore` / `.editorconfig` 这类点号开头的文件都能正确命中
- **多扩展名共用图标**：如 `xlsx` / `xls` / `csv` / `tsv` 共用表格图标，`tsx` / `jsx` 共用 React 图标
- **兜底不报错**：未登记的扩展名返回 `unknown` 图标，后台新增文件类型时前端不会缺图
- **尺寸自适应**：内部 svg 固定为 `1em`，直接用外层 `font-size` 控制大小

## 基础用法

```vue
<template>
  <FileIcon file-type="pdf" />
</template>

<script setup lang="ts">
  import { FileIcon } from '@blueking/chat-x';
</script>
```

**渲染效果**

## 从文件名推断

后台未下发 `type` 时传 `fileName` 即可，组件会取最后一段扩展名：

```vue
<template>
  <!-- 取 xlsx -->
  <FileIcon file-name="季度报告.final.xlsx" />
  <!-- 取 gitignore -->
  <FileIcon file-name=".gitignore" />
</template>
```

两者同时传入时以 `fileType` 优先。

## 控制尺寸

图标宽高为 `1em`，用外层 `font-size` 控制即可，无需改 svg：

```vue
<template>
  <span style="font-size: 16px"><FileIcon file-type="py" /></span>
  <span style="font-size: 32px"><FileIcon file-type="py" /></span>
</template>
```

## API

### Props

| 属性名   | 类型     | 必填 | 默认值      | 说明                                                     |
| -------- | -------- | ---- | ----------- | -------------------------------------------------------- |
| fileType | `string` | 否   | `undefined` | 文件类型：扩展名（如 `pdf` / `py`）或无扩展名文件名（如 `Dockerfile`） |
| fileName | `string` | 否   | `undefined` | 文件名，`fileType` 缺省时用于推断扩展名                    |

两者都不传时渲染兜底图标。

### Emits / Slots / Expose

- 无。

## 图标覆盖范围

| 图标 | 覆盖扩展名 |
| ---- | ---------- |
| 文档类 | `pptx` / `docx` / `pdf` / `txt` / `rst` / `md` / `markdown` / `tex` |
| 表格类 | `xlsx` / `xlsm` / `xls` / `csv` / `tsv` |
| 前端 | `html` / `htm` / `css` / `scss` / `less` / `js` / `mjs` / `cjs` / `ts` / `tsx` / `jsx` / `vue` / `xml` |
| 后端 / 系统 | `py` / `go` / `rs` / `rb` / `java` / `kt` / `swift` / `c` / `h` / `cpp` / `hpp` / `cs` / `php` / `lua` / `r` / `scala` / `dart` / `sql` / `sh` / `bash` / `zsh` / `ps1` |
| 配置 | `json` / `jsonc` / `yaml` / `yml` / `toml` / `ini` / `cfg` / `conf` / `env` / `editorconfig` / `Makefile` |
| 工具链 | `Dockerfile` / `dockerignore` / `gitignore` |
| 图片 | `png` / `jpg` / `jpeg` / `svg` |
| 兜底 | 以上之外的所有类型 |

新增类型时在 `src/icons/file-icons.ts` 的 `FILE_ICON_GROUPS` 里补一行即可；对应 svg 需先放进 `src/svgs/` 并按需 `?raw` 引入（只引实际用到的，避免把整个图标库打进产物）。

## 使用建议

- 图标颜色由 svg 自带，不继承 `currentColor`，不要试图用 `color` 覆盖
- 需要与文件名同行展示时，给父容器设 `display: flex` + `gap`，组件本身已是 `inline-flex` 且 `flex-shrink: 0`

## 关联组件

- [FileArtifactPanel](../message/file-artifact-panel.md) — 文件产物列表与预览头使用该组件。
- [AssistantMessage](../message/assistant-message.md) — 消息内文件产物卡片的图标来源。
