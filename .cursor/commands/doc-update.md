# 文档更新助手

## 核心目标

在 `ai-blueking` 组件开发和更新后，自动分析代码变更并同步更新：

1. **NPM 包更新日志**：`src/frontend/ai-blueking/CHANGELOG.md`
2. **文档站更新日志**：`src/frontend/web/docs/changelog.md`
3. **相关功能文档**：`src/frontend/web/docs/` 下的指南文档

## 使用方式

```bash
# 基于最近的 commits 更新
/doc-update --last <数量>

# 基于 commit 范围更新
/doc-update --from <hash> --to <hash>

# 基于分支差异更新
/doc-update --branch <分支名>

# 基于版本号更新（从 git tag 或 package.json 分析）
/doc-update --version <版本号>

# 基于功能描述手动更新
/doc-update <功能描述>
```

## 执行流程

### 第一步：变更分析

1. **获取变更内容**

   - 执行 git 命令获取指定范围的变更
   - 重点关注 `src/frontend/ai-blueking/` 目录下的文件变更
   - 提取 commit message、文件差异和代码变更

2. **智能分类识别**

   根据变更内容自动识别类型：

   | 变更特征                  | 分类          | 影响           |
   | ------------------------- | ------------- | -------------- |
   | 新增 Props/Methods/Events | ✨ 新增功能   | API 文档需更新 |
   | 修改现有 API 签名         | ⚠️ 破坏性变更 | 需迁移指南     |
   | 优化性能/体验             | 🛠️ 优化改进   | 描述性更新     |
   | 修复 bug                  | 🐛 Bug 修复   | 简要说明       |
   | 文档/注释变更             | 📝 文档更新   | 仅文档变更     |

3. **提取关键信息**
   - Props 变更：名称、类型、默认值、描述
   - Methods 变更：方法签名、参数、返回值
   - Events 变更：事件名、参数结构
   - 功能描述：用户可见的变化
   - 破坏性变更：不兼容的修改

### 第二步：版本号推断

根据变更类型自动推断版本号（遵循语义化版本）：

```javascript
// 当前版本：v1.3.1
破坏性变更 → v2.0.0 (MAJOR)
新增功能   → v1.4.0 (MINOR)
Bug修复/优化 → v1.3.2 (PATCH)
```

**检查点**：

- 读取 `ai-blueking/package.json` 获取当前版本
- 对比 git tags 确认版本号的连续性
- 提示用户确认推断的版本号

### 第三步：生成更新内容

#### 3.1 生成 ai-blueking/CHANGELOG.md 内容

格式规范：

`````markdown
## [版本号] - YYYY-MM-DD

> ⚠️ **重要提醒**：（如有破坏性变更或版本兼容要求）

### ✨ 新增功能

#### 功能分类标题（如：会话管理增强）

- **具体功能名称**：功能描述，说明用途和使用场景
- **Props/Methods/Events 变更**：具体的 API 变更

#### 代码示例（如果是重要功能）

````vue
<template>
  <!-- 完整的使用示例 -->
</template>
\``` ### 🛠️ 优化改进 #### 子分类（如：性能优化） - **优化项**：具体的优化内容和效果 ### 🐛 Bug 修复 - 修复具体问题的描述 -
修复问题产生的影响和现在的行为 ### ⚠️ 破坏性变更（如有） - **变更内容**：详细说明不兼容的修改 - **迁移指南**：如何从旧版本迁移到新版本
````
`````

````

#### 3.2 生成 web/docs/changelog.md 内容

格式规范（JavaScript 对象数组）：

```javascript
{
  version: "v1.x.x",
  date: "YYYY-MM-DD",
  important: "⚠️ <strong>重要提醒</strong>：版本兼容性说明（可选）",
  features: [
    "新增功能的简洁描述，使用 <code>标签</code> 标注代码",
    "支持 HTML 标签进行样式标注"
  ],
  improvements: [
    "优化改进的描述",
    "性能提升或体验优化"
  ],
  fixes: [
    "修复的 bug 描述"
  ],
  breaking: [
    "破坏性变更的说明（可选）"
  ]
}
```

**注意事项**：

- 两个文件的内容要保持信息一致，但格式不同
- `CHANGELOG.md` 更详细，包含代码示例
- `changelog.md` 更简洁，适合文档站展示
- 使用 `<code>` 标签标注 API 名称、配置项等

### 第四步：文档同步更新

文档更新分为两个层级：**NPM 包文档**和**VitePress 文档站**。

#### 4.1 NPM 包文档更新

根据变更类型，更新 `ai-blueking` 目录下的文档：

| 变更类型           | 需要更新的文件                                                                                   | 更新内容                                          |
| ------------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------- |
| 新增 Props         | `ai-blueking/readme.md` Props 表格                                                               | 添加新属性的行，包含名称、类型、默认值、描述      |
| 新增 Events        | `ai-blueking/readme.md` Events 表格                                                              | 添加新事件的行，包含事件名、参数、描述            |
| 新增 Methods       | `ai-blueking/readme.md` Methods 表格                                                             | 添加新方法的行，包含方法名、参数、返回值、描述    |
| 新增暴露属性       | `ai-blueking/readme.md` 暴露属性章节                                                             | 添加新属性的说明和使用示例                        |
| IShortcut 接口变更 | `ai-blueking/readme.md` 快捷操作章节<br/>`ai-blueking/src/types/index.ts` IShortcut 接口定义    | 更新接口定义和使用示例                            |
| 版本号更新         | `ai-blueking/package.json`<br/>`ai-blueking/readme.md` 徽章                                      | 同步更新版本号                                    |
| 功能增强           | `ai-blueking/readme.md` 对应功能章节                                                             | 添加新特性说明和使用示例                          |
| 破坏性变更         | `ai-blueking/readme.md` 所有相关章节<br/>可能需要创建迁移指南                                    | 明确标注不兼容变更，提供迁移方案                  |

#### 4.2 VitePress 文档站更新

VitePress 文档站位于 `web/docs/` 目录，包含以下主要文件结构：

```
web/docs/
├── api/                          # API 参考文档
│   ├── types.md                 # 类型定义（IShortcut, IAgentInfo 等）
│   ├── props.md                 # Props 属性文档
│   ├── methods.md               # Methods 方法文档
│   └── events.md                # Events 事件文档
├── guide/                        # 使用指南
│   ├── core-features/           # 核心功能
│   │   ├── shortcuts.md        # 快捷操作指南
│   │   ├── content-referencing.md  # 内容引用
│   │   ├── prompts.md          # Prompt 功能
│   │   └── ui-customization.md # UI 定制
│   └── advanced-usage/          # 高级用法
│       ├── session-lifecycle.md # 会话生命周期
│       ├── programmatic-interaction.md # 编程式交互
│       └── custom-requests.md   # 自定义请求
└── changelog.md                  # 文档站更新日志
```

**VitePress 文档更新映射表**：

| 变更类型              | 需要更新的 VitePress 文档                                    | 更新内容                                             |
| --------------------- | ------------------------------------------------------------ | ---------------------------------------------------- |
| IShortcut 接口变更    | `api/types.md` IShortcut 接口定义<br/>`guide/core-features/shortcuts.md` 快捷操作指南 | 更新接口定义，添加版本标注，提供使用示例和场景说明   |
| 新增 Props            | `api/props.md` Props 列表                                    | 添加新属性行，包含版本 Badge，详细说明和使用场景     |
| 新增 Methods          | `api/methods.md` Methods 列表                                | 添加新方法，包含版本 Badge，参数说明和完整示例       |
| 新增 Events           | `api/events.md` Events 列表                                  | 添加新事件，说明触发时机和参数结构                   |
| 新增暴露属性          | `api/props.md` 暴露属性章节<br/>`api/types.md` 相关类型定义 | 添加属性说明、字段说明、使用示例和适用场景           |
| Props 功能增强        | `api/props.md` 对应属性说明                                  | 添加版本 Badge，更新描述，补充增强功能说明           |
| 快捷操作功能增强      | `guide/core-features/shortcuts.md`                           | 添加新特性章节，包含详细说明、多个实际示例和最佳实践 |
| 会话管理功能变更      | `guide/advanced-usage/session-lifecycle.md`                  | 更新会话管理流程，补充新 API 说明                    |
| 编程式交互功能变更    | `guide/advanced-usage/programmatic-interaction.md`           | 更新交互方法，提供新的使用示例                       |
| 请求配置功能变更      | `guide/advanced-usage/custom-requests.md`                    | 更新配置说明，补充新的配置选项                       |
| 破坏性变更            | 所有相关文档 + `guide/migration-x.x.md`（如需要）           | 明确标注不兼容变更，创建独立的迁移指南               |

**VitePress 文档特殊要求**：

1. **版本标注**：所有新增或变更的内容必须添加版本 Badge
   ```markdown
   <Badge type="tip" text="v1.3.2" />           # 新增功能
   <Badge type="tip" text="v1.3.2 增强" />      # 功能增强
   <Badge type="info" text="v1.3.2" />          # 信息性变更
   <Badge type="warning" text="已废弃" />       # 废弃警告
   <Badge type="danger" text="破坏性变更" />    # 破坏性变更
   ```

2. **代码示例格式**：
   - 使用 Vue 3 Composition API 作为主要示例
   - 提供完整可运行的代码
   - 添加必要的注释说明
   - 使用 `:::code-group` 提供 Vue 2/Vue 3 对比示例

3. **内容组织**：
   - API 文档：简洁的参数说明 + 类型定义
   - 指南文档：详细的使用说明 + 多个实际示例 + 使用场景 + 最佳实践

4. **链接引用**：
   - 使用相对路径引用其他文档
   - 确保内部链接的准确性
   - 提供相关文档的交叉引用

**自动化检测建议**：

- 扫描变更的文件路径，智能提示可能需要更新的文档
- 根据代码变更类型，生成文档更新模板
- 对于新增的 API，自动生成基础文档结构
- 对于破坏性变更，强制要求更新迁移说明
- 检查版本 Badge 的正确使用

### 第五步：一致性验证

执行以下检查确保文档质量：

#### 5.1 版本号一致性

- [ ] `ai-blueking/package.json` - version 字段
- [ ] `ai-blueking/CHANGELOG.md` - 顶部版本号（如 `## [1.3.2] - 2026-01-09`）
- [ ] `ai-blueking/readme.md` - 版本徽章（如 `版本-1.3.2-blue`）
- [ ] `web/docs/changelog.md` - changelogData 数组第一项的 version（如 `"v1.3.2"`）

#### 5.2 内容信息一致性

**两份 CHANGELOG 必须保持信息一致**：

| 文档                                | 格式       | 详细程度                   | 特点                                |
| ----------------------------------- | ---------- | -------------------------- | ----------------------------------- |
| `ai-blueking/CHANGELOG.md`          | Markdown   | 详细，包含代码示例         | 用于 NPM 包，开发者查看             |
| `web/docs/changelog.md`             | JavaScript | 简洁，HTML 标签格式化      | 用于文档站，用户浏览                |

**检查要点**：
- [ ] 功能描述的核心信息一致
- [ ] 使用 `<code>` 标签标注 API 名称（仅 changelog.md）
- [ ] 重要提醒内容一致
- [ ] 日期格式统一为 YYYY-MM-DD

#### 5.3 API 文档一致性

**NPM 包文档与 VitePress 文档站必须同步**：

| 变更类型         | NPM 包文档                            | VitePress 文档站                 | 检查要点                           |
| ---------------- | ------------------------------------- | -------------------------------- | ---------------------------------- |
| IShortcut 接口   | `readme.md` 接口定义和示例            | `api/types.md` + `shortcuts.md`  | 接口字段定义一致，示例使用新字段   |
| Props 属性       | `readme.md` Props 表格                | `api/props.md` Props 列表        | 属性名、类型、默认值、描述一致     |
| Methods 方法     | `readme.md` Methods 表格              | `api/methods.md` Methods 列表    | 方法签名、参数、返回值一致         |
| Events 事件      | `readme.md` Events 表格               | `api/events.md` Events 列表      | 事件名、参数结构一致               |
| 暴露属性         | `readme.md` 暴露属性章节              | `api/props.md` 暴露属性章节      | 属性说明和使用示例一致             |
| 使用示例         | `readme.md` 高级用法章节              | `guide/` 对应指南文档            | 示例代码使用最新 API               |

#### 5.4 VitePress 文档特定检查

- [ ] **版本 Badge 正确使用**：
  - 新增功能：`<Badge type="tip" text="v1.3.2" />`
  - 功能增强：`<Badge type="tip" text="v1.3.2 增强" />`
  - 废弃功能：`<Badge type="warning" text="已废弃" />`

- [ ] **代码块格式正确**：
  ```markdown
  # 正确的代码块格式
  ```vue
  <template>
    <AIBlueking :url="apiUrl" />
  </template>

  <script setup>
  import { ref } from 'vue'
  // ...
  </script>
  \```
  ```

- [ ] **内部链接有效**：
  ```markdown
  # 使用相对路径
  [快捷操作指南](/guide/core-features/shortcuts)
  [Props 文档](/api/props)
  ```

- [ ] **章节结构清晰**：
  - API 文档：参数说明 → 使用示例 → 注意事项
  - 指南文档：功能介绍 → 详细说明 → 实际示例 → 使用场景 → 最佳实践

#### 5.5 代码示例质量检查

- [ ] **示例完整性**：
  - 包含必要的 import 语句
  - 包含完整的 template 和 script
  - 变量定义完整，无遗漏

- [ ] **示例可运行性**：
  - 接口名称正确（如 `IShortcut` 而非 `ShortCut`）
  - API 调用方式正确
  - 数据结构符合最新定义

- [ ] **示例多样性**：
  - 提供基础使用示例
  - 提供高级用法示例
  - 必要时提供 Vue 2/Vue 3 对比示例

- [ ] **注释清晰度**：
  - 关键代码添加注释说明
  - 复杂逻辑提供解释
  - 版本相关变更标注版本号

#### 5.6 格式规范性检查

- [ ] **Markdown 格式**：
  - 标题层级正确（从 ## 开始，依次递进）
  - 列表缩进一致
  - 代码块有语言标识
  - 表格格式对齐

- [ ] **JavaScript 对象格式**（changelog.md）：
  - 对象语法正确
  - 字符串使用双引号
  - 数组逗号规范
  - 缩进统一为 2 空格

- [ ] **日期格式统一**：
  - 统一使用 YYYY-MM-DD 格式
  - 如：2026-01-09

- [ ] **标点符号规范**：
  - 中文内容使用中文标点
  - 代码和英文使用英文标点
  - 列表项末尾不加句号（除非是完整句子）

## 输出格式

完成分析和更新后，输出以下内容：

### 1. 变更摘要

```
📊 变更分析报告

版本号：v1.x.x → v1.y.z
变更类型：新增功能 / 优化改进 / Bug修复 / 破坏性变更

核心变更：
✨ 新增功能 (X项)
  - 功能1：描述
  - 功能2：描述

🛠️ 优化改进 (X项)
  - 优化1：描述

🐛 Bug修复 (X项)
  - 修复1：描述

⚠️ 破坏性变更 (X项)
  - 变更1：描述
```

### 2. 文档更新清单

```
📝 文档更新清单

必须更新：
✅ ai-blueking/CHANGELOG.md - 已生成更新内容
✅ web/docs/changelog.md - 已生成更新内容
✅ ai-blueking/package.json - 需手动更新版本号

建议更新：
⚠️ ai-blueking/readme.md - 新增 API 需补充到表格
⚠️ web/docs/guide/xxx.md - 相关功能文档需同步

无需更新：
- 其他文档未受影响
```

### 3. 具体更新内容

直接展示生成的 CHANGELOG 内容，分别对应两个文件的格式。

### 4. 后续操作提示

```
🎯 后续操作

1. 审查生成的 CHANGELOG 内容是否准确
2. 更新 package.json 中的版本号为 v1.y.z
3. 检查并更新相关的 API 文档
4. 提交更新：git commit -m "docs: update changelog for v1.y.z"
5. 创建版本标签：git tag v1.y.z
```

## 常见场景快速指南

### 场景 1：发布新版本前的文档检查

```bash
# 分析从上个版本到现在的所有变更
/doc-update --version v1.3.1

# 系统会自动：
# 1. 对比 v1.3.1 tag 到 HEAD 的所有变更
# 2. 生成完整的 CHANGELOG
# 3. 检查文档一致性
# 4. 推断新版本号
```

### 场景 2：功能开发完成后的文档更新

```bash
# 分析最近的几个 commits
/doc-update --last 3

# 或指定功能分支
/doc-update --branch feature/new-session-api
```

### 场景 3：紧急 Bug 修复的文档更新

```bash
# 快速更新，只需描述修复内容
/doc-update 修复了会话切换时的内存泄漏问题

# 系统会自动：
# 1. 识别为 Bug 修复（PATCH 版本）
# 2. 生成简洁的 CHANGELOG 条目
# 3. 更新版本号建议
```

## 注意事项与最佳实践

### ⚠️ 必须注意

1. **双份 CHANGELOG 都要更新**

   - `ai-blueking/CHANGELOG.md` - NPM 包用户看到的
   - `web/docs/changelog.md` - 文档网站展示的

2. **破坏性变更必须明确标注**

   - 在两份 CHANGELOG 中都要突出显示
   - 提供详细的迁移指南
   - 更新相关的 API 文档说明旧版本行为

3. **版本号要同步更新**
   - package.json
   - CHANGELOG 顶部
   - readme.md 徽章
   - git tag

### 💡 最佳实践

1. **每次功能开发完成后立即更新文档**

   - 记忆最清晰时写文档最准确
   - 避免版本发布前集中更新遗漏细节

2. **使用详细的 commit message**

   - 遵循 Conventional Commits 规范
   - 方便自动化工具分析变更类型

3. **保持示例代码最新**

   - 每次 API 变更都检查所有示例
   - 确保示例代码可以直接运行

4. **文档结构保持一致**
   - 新增功能按照现有结构组织
   - 保持术语和描述风格统一

## 附录

### 附录 A：快速检查清单

每次更新文档时，使用此清单确保不遗漏：

```
文档更新检查清单：

【前置检查】
□ 已确认代码变更的范围和类型
□ 已确定目标版本号（MAJOR.MINOR.PATCH）
□ 已准备好变更的详细描述
□ 已识别变更的影响范围

【必须更新 - NPM 包文档】
□ ai-blueking/CHANGELOG.md - 添加新版本条目，包含详细说明和代码示例
□ ai-blueking/package.json - 更新 version 字段为新版本号
□ ai-blueking/readme.md - 更新版本徽章

【必须更新 - 文档站】
□ web/docs/changelog.md - 添加新版本对象（JavaScript 格式）

【按需更新 - NPM 包文档】
□ ai-blueking/readme.md - Props 表格（如有新增或变更）
□ ai-blueking/readme.md - Events 表格（如有新增或变更）
□ ai-blueking/readme.md - Methods 表格（如有新增或变更）
□ ai-blueking/readme.md - 暴露属性章节（如有新增）
□ ai-blueking/readme.md - 快捷操作章节（如有 IShortcut 变更）
□ ai-blueking/src/types/index.ts - TypeScript 类型定义

【按需更新 - VitePress 文档站】
□ web/docs/api/types.md - IShortcut 等类型定义（如有接口变更）
□ web/docs/api/props.md - Props 列表和说明（如有新增或变更）
□ web/docs/api/methods.md - Methods 列表和说明（如有新增）
□ web/docs/api/events.md - Events 列表和说明（如有新增）
□ web/docs/guide/core-features/shortcuts.md - 快捷操作指南（如有功能变更）
□ web/docs/guide/advanced-usage/*.md - 高级用法文档（如有相关变更）

【内容一致性验证】
□ 两份 CHANGELOG 核心信息一致（格式可不同）
□ NPM 包 readme.md 与 VitePress 文档站的 API 信息一致
□ 版本号在所有文件中同步（package.json, CHANGELOG, readme, changelog）
□ 所有示例代码使用最新的 API 和接口名称

【VitePress 特定检查】
□ 所有新增/变更内容添加了版本 Badge
□ 代码示例完整且可运行
□ 内部链接路径正确
□ 章节结构清晰合理

【格式规范检查】
□ Markdown 语法正确（标题层级、列表格式、代码块）
□ JavaScript 对象格式正确（changelog.md）
□ 日期格式统一为 YYYY-MM-DD
□ 中英文标点符号使用规范

【质量检查】
□ 所有代码示例已测试通过
□ 技术术语使用准确一致
□ 文档描述清晰易懂
□ 无拼写和语法错误

【提交准备】
□ 运行 linter 检查所有文档文件
□ 预览文档站确保显示正确
□ 文档 commit 与代码 commit 分开
□ commit message 清晰描述变更（如：docs: update changelog for v1.3.2）
□ 创建对应的 git tag（如：v1.3.2）
```

### 附录 B：实际更新示例

#### 示例 1：新增快捷指令字段（v1.3.2）

**变更内容**：IShortcut 接口新增 `alias`、`enableFillBack` 字段，组件新增 `fillRegx` 字段

**更新的文件**：

1. **NPM 包文档**：
   - `package.json`: 版本号 1.3.1 → 1.3.2
   - `CHANGELOG.md`: 添加 v1.3.2 章节，包含详细说明和代码示例
   - `readme.md`:
     - 更新版本徽章
     - 更新 IShortcut 接口定义，添加新字段注释
     - 添加新字段的使用示例

2. **VitePress 文档站**：
   - `changelog.md`: 添加 v1.3.2 版本对象
   - `api/types.md`:
     - 更新 IShortcut 接口，添加 `<Badge type="tip" text="v1.3.2" />`
     - 新增"v1.3.2 新增字段说明"章节
   - `guide/core-features/shortcuts.md`:
     - 更新"快捷操作的新特性"列表
     - 更新 IShortcut 接口定义
     - 新增"快捷指令增强功能 (v1.3.2)"完整章节

**关键点**：
- 接口定义在所有文档中保持一致
- VitePress 文档提供更详细的使用场景和示例
- 所有新增内容标注版本 Badge

#### 示例 2：新增暴露属性（v1.3.2）

**变更内容**：组件实例新增 `agentInfo` 暴露属性

**更新的文件**：

1. **NPM 包文档**：
   - `CHANGELOG.md`: 在"新增功能"章节添加 agentInfo 说明
   - `readme.md`:
     - 在"暴露属性"章节添加 agentInfo 表格行
     - 添加 agentInfo 使用示例

2. **VitePress 文档站**：
   - `changelog.md`: 在 features 数组添加简短描述
   - `api/props.md`:
     - 重构"暴露属性"章节，添加 agentInfo 完整说明
     - 包含字段说明、使用示例、使用场景
   - `api/types.md`:
     - 在 IAgentInfo 章节添加"智能体信息访问"说明

**关键点**：
- 说明属性的用途和包含的字段
- 提供完整的使用示例代码
- 列出实际的使用场景

#### 示例 3：Props 功能增强（v1.3.2）

**变更内容**：`enablePopup` prop 现在与智能体配置联动控制

**更新的文件**：

1. **NPM 包文档**：
   - `CHANGELOG.md`: 在"优化改进"章节说明划词 Popup 逻辑优化
   - `readme.md`: Props 表格中 enablePopup 的描述（如需要）

2. **VitePress 文档站**：
   - `changelog.md`: 在 improvements 数组添加描述
   - `api/props.md`:
     - enablePopup 行添加 `<Badge type="tip" text="v1.3.2 增强" />`
     - 新增"划词弹窗控制增强 (v1.3.2)"专门章节
     - 包含控制优先级、配置示例、使用场景

**关键点**：
- 对于功能增强，添加 "v1.3.2 增强" Badge
- 详细说明增强的逻辑和控制规则
- 提供多个实际配置场景示例

### 附录 C：常见错误和解决方案

| 错误类型                   | 表现                                 | 解决方案                                           |
| -------------------------- | ------------------------------------ | -------------------------------------------------- |
| 版本号不一致               | 不同文件中版本号不匹配               | 检查 package.json, CHANGELOG, readme, changelog   |
| 接口定义不一致             | NPM 文档和 VitePress 文档定义不同    | 确保两处的接口字段和类型完全一致                   |
| 忘记添加版本 Badge         | VitePress 文档新内容没有版本标注     | 为所有新增/变更内容添加对应的 Badge                |
| 代码示例不可运行           | 示例代码缺少导入或使用旧 API         | 确保示例完整，使用最新 API，测试可运行性           |
| changelog.md 格式错误      | JavaScript 对象语法错误              | 检查引号、逗号、数组格式                           |
| 内部链接失效               | VitePress 文档链接到不存在的页面     | 使用相对路径，确保目标文件存在                     |
| 两份 CHANGELOG 信息不一致  | 核心功能描述不同                     | 对比两份文档，确保信息一致（格式可不同）           |
| 忘记更新 readme 徽章       | readme 顶部版本徽章显示旧版本        | 更新徽章 URL 中的版本号                            |
| 日期格式不统一             | 部分使用 MM/DD/YYYY，部分 YYYY-MM-DD | 统一使用 YYYY-MM-DD 格式                           |
| 示例代码格式不规范         | 缩进混乱，缺少必要注释               | 统一使用 2 空格缩进，添加清晰注释                  |

### 附录 D：文档更新最佳实践

1. **先理解变更，再写文档**
   - 完全理解代码变更的目的和影响
   - 确认变更的使用场景和适用范围
   - 思考用户如何使用这个新功能

2. **从用户角度写文档**
   - 使用清晰、简洁的语言
   - 提供实际可运行的示例
   - 说明功能的适用场景和使用价值
   - 提供最佳实践建议

3. **保持文档一致性**
   - API 定义在所有文档中保持一致
   - 使用统一的技术术语
   - 保持示例代码风格一致
   - 版本标注规范统一

4. **注重文档质量**
   - 示例代码必须可运行
   - 避免拼写和语法错误
   - 确保技术描述准确
   - 定期审查和更新文档

5. **及时更新文档**
   - 在功能开发完成后立即更新文档
   - 不要积压多个功能一起更新
   - 记忆清晰时文档质量更高

6. **善用版本控制**
   - 文档更新使用独立的 commit
   - commit message 清晰描述文档变更
   - 使用 git tag 标记版本
   - 便于追踪文档变更历史

---

**使用此命令时，请提供：**

- Git commit 范围/分支/版本号
- 或者直接描述本次更新的功能/修复内容

系统将自动分析变更并生成标准化的文档更新内容。
````
