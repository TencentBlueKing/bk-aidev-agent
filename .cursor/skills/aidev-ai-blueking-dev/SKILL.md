---
name: aidev-ai-blueking-dev
description: 本地开发和构建部署 aidev-ai-blueking（AI 小鲸）前端组件到 Django 模板项目的完整流程。涵盖 publish-template 前端开发、Python 包构建部署、常见问题排查。触发场景：构建 ai-blueking、部署小鲸、publish-template 开发调试、make build/deploy-aidev-ai-blueking、Django 模板项目本地运行。
---

# AI 小鲸本地开发与构建部署

## 项目架构

```
src/frontend/
├── publish-template/          # 前端构建模板（pnpm dev 本地开发 / pnpm build 生产构建）
├── ai-blueking/               # 旧版小鲸组件（workspace 包，逐步废弃）
└── bkui-chat-x/               # 新版小鲸组件 monorepo（独立 workspace）
    └── packages/ai-blueking/  # @blueking/ai-blueking 新架构

src/plugins/aidev_ai_blueking/ # Python 包（包含构建后的前端静态文件）

template/builtin/{{cookiecutter.project_name}}/  # Django 模板项目（最终运行环境）
```

### 依赖关系

- `publish-template` 通过 npm 依赖 `@blueking/ai-blueking`（固定版本，非 workspace 链接）
- Django 模板项目通过 pip 依赖 `aidev-ai-blueking` Python 包（内含前端构建产物）

## 快速命令

| 场景 | 命令 | 工作目录 |
|------|------|----------|
| 前端本地开发 | `pnpm dev` | `src/frontend/publish-template/` |
| 构建+部署一键完成 | `make deploy-aidev-ai-blueking` | 项目根目录 |
| 仅构建 Python 包 | `make build-aidev-ai-blueking` | 项目根目录 |
| 启动 Django 服务 | `make dev` | `template/builtin/{{cookiecutter.project_name}}/` |

## 前端本地开发（publish-template）

```bash
cd src/frontend/publish-template/
pnpm install
pnpm dev     # 端口 5005
```

环境变量配置：
- `.bk.env` — 所有环境通用（`BK_API_PREFIX` 等）
- `.bk.development.env` — 开发模式专用（`BK_STATIC_URL` 等）

## 构建部署流程

### 一键命令

```bash
# 项目根目录执行，自动完成：清缓存 → pnpm install → build → uv build → 安装到 .venv
make deploy-aidev-ai-blueking
```

### 手动分步

```bash
# 1. 构建
make build-aidev-ai-blueking

# 2. 安装到模板项目的 .venv
cd template/builtin/{{cookiecutter.project_name}}/
UV_PROJECT_ENVIRONMENT=.venv uv pip install --reinstall \
  ../../../src/plugins/aidev_ai_blueking/dist/aidev_ai_blueking-*.tar.gz

# 3. 启动 Django 验证
make dev    # 端口 5000
```

## 关键注意事项

### .venv vs conda/系统 Python

模板项目的 Makefile 使用 `uv run` 启动 Django，**始终使用项目目录下的 `.venv`**，与 shell 中激活的 conda 环境无关。

安装包时**必须指向 `.venv`**：

```bash
# 正确 — 装到 .venv
UV_PROJECT_ENVIRONMENT=.venv uv pip install --reinstall <tarball>

# 错误 — 装到 conda，Django 用不到
conda activate xxx && uv pip install <tarball>
```

### webpack 缓存

`publish-template/node_modules/.cache/webpack/` 可能缓存旧版组件代码。`pnpm dev`（热加载）不受影响，但 `pnpm build`（生产构建）会命中缓存导致产物过时。

Makefile 已包含 `rm -rf node_modules/.cache` 步骤。如果手动运行 `pnpm build`，需先清缓存：

```bash
rm -rf node_modules/.cache && pnpm run build
```

### 添加前端路由

新增前端页面路由后，需同步更新 Django URL 配置，否则刷新页面 404：

文件：`src/plugins/aidev_ai_blueking/aidev_ai_blueking/urls.py`

```python
urlpatterns = [
    re_path(r"^$", IndexView.as_view(), name="index"),
    re_path(r"^page/$", IndexView.as_view(), name="index"),
    re_path(r"^side-slider/$", IndexView.as_view(), name="index"),
    re_path(r"^chat-window/$", IndexView.as_view(), name="index"),
    # 新增路由在此添加，统一指向 IndexView（SPA 模式）
]
```

### pnpm-lock.yaml 不一致

如果 `package.json` 中依赖版本更新但 lock 文件未同步，`pnpm install` 会报 `ERR_PNPM_OUTDATED_LOCKFILE`。Makefile 已使用 `--no-frozen-lockfile` 参数自动处理。

## 排查清单

组件表现不一致时按此排查：

1. **webpack 缓存**：`rm -rf src/frontend/publish-template/node_modules/.cache`
2. **装错环境**：确认用 `UV_PROJECT_ENVIRONMENT=.venv` 安装，而非 conda
3. **旧 dist 残留**：检查 `src/plugins/aidev_ai_blueking/dist/` 是否有多个 tarball
4. **lock 文件过期**：`cd src/frontend && pnpm install --no-frozen-lockfile`
5. **Django 路由缺失**：检查 `urls.py` 是否包含对应前端路由
