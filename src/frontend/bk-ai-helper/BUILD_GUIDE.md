# bk-ai-helper 构建指南

## 版本区分

`@blueking/bk-ai-helper` 支持内部版和外部版两种构建方式，通过 `BUILD_TYPE` 环境变量进行控制。

### 外部版（开源版本）

**特点：**

- baseUrl 默认值为空字符串 `""`
- 强制忽略所有环境变量和 .env 文件中的值
- 适用于开源版本，用户需要自行配置 AI 服务的 baseUrl
- 发布到 npm 官方 registry

**构建命令：**

```bash
# 一键构建外部版（自动设置 baseUrl 为空字符串）
pnpm run build:external
```

**输出目录：**
构建产物会输出到 `dist/vue2` 和 `dist/vue3` 目录。

**发布命令：**

```bash
# 一键发布外部版（包含构建、验证、发布、清理）
pnpm run publish:external
```

发布脚本会自动执行以下步骤：

1. 清理旧的构建产物
2. 构建外部版（baseUrl 为空字符串）
3. 验证 baseUrl 为空字符串
4. 检查 registry 配置
5. 确认发布（需要输入 yes）
6. 发布到 npm 官方源
7. 自动清理 dist 目录

⚠️ **安全特性**：

- 发布前会自动验证构建类型，防止误发布
- 发布后自动清理 dist 目录
- 即使发布失败也会清理 dist 目录

### 内部版（腾讯内部版本）

**特点：**

- baseUrl 必须从 `.env` 文件中读取 `AI_HELPER_BASE_URL`
- 如果 `.env` 文件中没有设置或值为空，构建会失败并提示错误
- 开箱即用，无需额外配置
- 发布到腾讯内部 npm 镜像源

**前置要求：**
必须在项目根目录创建 `.env` 文件，并设置 `AI_HELPER_BASE_URL`：

```bash
# 创建 .env 文件
echo "AI_HELPER_BASE_URL=https://your-internal-ai-service.com" > .env
```

**构建命令：**

```bash
# 构建内部版（从 .env 文件读取 AI_HELPER_BASE_URL）
pnpm run build:internal
```

**⚠️ 重要提示：**

- 如果 `.env` 文件不存在或 `AI_HELPER_BASE_URL` 未设置，构建会失败并显示错误提示
- `.env` 文件已在 `.gitignore` 中，不会被提交到代码仓库
- 内部版构建会忽略系统环境变量中的 `AI_HELPER_BASE_URL`，只从 `.env` 文件读取

**构建失败示例：**

```bash
$ pnpm run build:internal

Error: 内部版构建失败：必须在 .env 文件中设置 AI_HELPER_BASE_URL 环境变量
请确保项目根目录存在 .env 文件，并包含：AI_HELPER_BASE_URL=你的AI服务地址
```

**发布命令：**

```bash
# 一键发布内部版（包含构建、验证、发布、清理）
pnpm run publish:internal
```

发布脚本会自动执行以下步骤：

1. 清理旧的构建产物
2. 构建内部版（从 .env 文件读取 AI_HELPER_BASE_URL）
3. 验证 baseUrl 不为空
4. 检查 registry 配置
5. 确认发布（需要输入 yes）
6. 发布到腾讯内部 npm 镜像源
7. 自动清理 dist 目录（避免敏感信息残留）

⚠️ **安全特性**：

- 发布前会自动验证构建类型，防止误发布
- 发布后自动清理 dist 目录，避免敏感信息残留
- 即使发布失败也会清理 dist 目录

### 💡 构建类型说明

构建脚本通过 `BUILD_TYPE` 环境变量区分构建类型：

- **`build:external`**：设置 `BUILD_TYPE=external`，强制使用空字符串作为 baseUrl
- **`build:internal`**：设置 `BUILD_TYPE=internal`，必须从 `.env` 文件读取 `AI_HELPER_BASE_URL`

**使用示例：**

```bash
# 构建外部版（无需任何配置）
pnpm run build:external

# 构建内部版（必须先在 .env 文件中设置 AI_HELPER_BASE_URL）
echo "AI_HELPER_BASE_URL=https://internal-api.example.com" > .env
pnpm run build:internal
```

## 使用方式

### 外部版使用

```typescript
import { BkAiHelper } from '@blueking/bk-ai-helper/vue3';

// 需要手动配置 AI 服务的 baseUrl
<BkAiHelper baseUrl="https://your-ai-service.com" />
```

### 内部版使用

```typescript
import { BkAiHelper } from '@blueking/bk-ai-helper/vue3';

// 无需配置 baseUrl，使用构建时内置的敏感地址
<BkAiHelper />
```

## 实现原理

### 1. 构建类型区分

构建脚本通过 `BUILD_TYPE` 环境变量区分构建类型：

- `BUILD_TYPE=external`：外部版构建，强制使用空字符串
- `BUILD_TYPE=internal`：内部版构建，从 `.env` 文件读取值

### 2. 环境变量处理逻辑

在 `scripts/vite.utils.ts` 中，`getAiHelperBaseUrl` 函数根据构建类型处理：

**外部版处理：**

```typescript
if (buildType === "external") {
  // 强制使用空字符串，忽略所有环境变量和 .env 文件
  return ""
}
```

**内部版处理：**

```typescript
if (buildType === "internal") {
  // 临时删除环境变量，确保只从 .env 文件读取
  const envFromFile = loadEnv(process.env.NODE_ENV || "production", process.cwd(), "")
  const baseUrl = envFromFile.AI_HELPER_BASE_URL

  if (!baseUrl || baseUrl.trim() === "") {
    throw new Error("内部版构建失败：必须在 .env 文件中设置 AI_HELPER_BASE_URL 环境变量")
  }

  return baseUrl
}
```

### 3. 环境变量注入

通过 Vite 的 `define` 选项将处理后的值注入到构建产物中：

```typescript
define: {
  AI_HELPER_BASE_URL: JSON.stringify(aiHelperBaseUrl),
}
```

### 4. 类型声明

在 `src/vite-env.d.ts` 中声明全局变量：

```typescript
declare const AI_HELPER_BASE_URL: string
```

### 5. 默认值设置

在 `src/index.vue` 中使用内置值作为 baseUrl 的默认值：

```typescript
const props = withDefaults(defineProps<{ baseUrl?: string }>(), {
  baseUrl: AI_HELPER_BASE_URL || "",
})
```

## 验证构建结果

### 检查输出目录

构建产物会输出到以下目录：

```
dist/
├── vue2/
│   ├── index.es.min.js
│   ├── index.umd.min.js
│   ├── index.iife.min.js
│   └── style.css
└── vue3/
    ├── index.es.min.js
    ├── index.umd.min.js
    ├── index.iife.min.js
    └── style.css
```

### 检查 baseUrl 默认值

可以通过以下方式验证构建是否正确：

```bash
# 构建后检查 baseUrl 的默认值
node -e "const fs = require('fs'); const content = fs.readFileSync('dist/vue3/index.es.min.js', 'utf8'); const match = content.match(/baseUrl:\s*\{\s*default:\s*\"([^\"]*)\"/); console.log('baseUrl default value:', match ? match[1] : 'not found');"
```

**外部版输出：**

```
baseUrl default value:
```

**内部版输出：**

```
baseUrl default value: https://your-internal-ai-service.com
```

⚠️ **注意**：实际的内部 AI 服务地址应该是敏感的私有地址，在开源代码中不应出现。

## 注意事项

1. **敏感信息保护**：
   - `.env` 文件已在 `.gitignore` 中，不会被提交到代码仓库
   - 内部版的 `AI_HELPER_BASE_URL` 应该仅在内部 CI/CD 或受保护的环境中使用
   - 避免在开源环境中暴露敏感的 AI 服务地址

2. **构建类型要求**：
   - **外部版**：强制使用空字符串，忽略所有环境变量和 `.env` 文件
   - **内部版**：必须从 `.env` 文件读取 `AI_HELPER_BASE_URL`，如果缺失或为空会构建失败

3. **环境变量优先级**：
   - 内部版构建时，系统环境变量中的 `AI_HELPER_BASE_URL` 会被忽略，只从 `.env` 文件读取
   - 如果同时设置了组件的 `baseUrl` prop，组件的 prop 会覆盖内置值

4. **构建时确定**：baseUrl 的默认值在构建时确定，一旦构建完成无法修改

5. **源码安全**：敏感的 baseUrl 通过 `.env` 文件控制，不会直接写在源码中，符合开源要求

6. **输出目录**：构建产物统一输出到 `dist/vue2` 和 `dist/vue3` 目录，不再直接输出到项目根目录

7. **registry 区分**：
   - 内部版使用 `https://mirrors.tencent.com/npm` 作为包发布地址
   - 外部版使用 `https://registry.npmjs.org/` 作为包发布地址（npm 默认）

8. **使用场景**：
   - 外部版：开源社区，部署到外部环境，用户需要自行配置 baseUrl
   - 内部版：腾讯内部项目，直接集成到内部系统，baseUrl 内置在构建产物中

9. **安全发布**：
   - 使用 `pnpm run publish:external` 或 `pnpm run publish:internal` 进行发布
   - 发布脚本会自动验证构建类型，防止误发布
   - 发布后自动清理 dist 目录，避免敏感信息残留
   - 即使发布失败也会清理 dist 目录
   - 可以通过设置 `SKIP_CONFIRM=true` 环境变量跳过确认步骤（CI/CD 场景）
