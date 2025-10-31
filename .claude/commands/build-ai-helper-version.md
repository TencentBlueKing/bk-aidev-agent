构建指定版本的 bk-ai-helper 模块（自动化版本）

自动化构建内部版或外部版的 bk-ai-helper 模块：
- 内部版：一键构建，自动配置敏感 AI 服务地址，发布到腾讯 npm 镜像
- 外部版：一键构建，baseUrl 置空，适合开源使用，发布到 npm 官方源

## 使用方法

### 构建外部版（自动化）
```bash
/export-ai-helper
# 等价于：pnpm run build:external
# 无需任何环境变量配置
```

### 构建内部版（自动化）
```bash
/internal-ai-helper
# 等价于：pnpm run build:internal
# 自动从 INTERNAL_AI_URL 环境变量读取，或使用默认值
```

## 详细说明

**外部版自动化构建：**
- 脚本自动设置 `AI_HELPER_BASE_URL=""`
- 一条命令完成，无需手动配置环境变量
- 发布到 npm 官方源

**内部版自动化构建：**
- 脚本自动设置 `AI_HELPER_BASE_URL="${INTERNAL_AI_URL:-默认值}"`
- 支持从环境变量读取敏感 AI 服务地址
- 如未设置环境变量，使用脚本中的默认值（仅用于测试）
- 发布到腾讯内部 npm 镜像源 (https://mirrors.tencent.com/npm)
- ⚠️ 生产环境建议在 CI/CD 系统中设置 INTERNAL_AI_URL 环境变量

**使用示例：**
```bash
# 方式1：直接构建外部版
pnpm run build:external

# 方式2：构建内部版（使用环境变量中的地址）
export INTERNAL_AI_URL="https://my-internal-ai.example.com"
pnpm run build:internal

# 方式3：构建内部版（使用脚本默认值，仅测试用）
pnpm run build:internal
```
