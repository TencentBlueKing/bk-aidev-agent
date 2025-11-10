# AI 小鲸后台服务

本插件需与智能体模板配合使用，用于开发和管理智能体插件。

## 本地调试智能体插件

### 环境准备

在开始前，请确保已安装以下工具：
- `uv`: Python 包管理工具
- `cookiecutter`: 项目模板工具

### SDK 打包

在 Git 仓库根目录执行以下命令，构建小鲸智能体插件：

```bash
make build-aidev-bkplugin
```

### 生成测试智能体

使用 cookiecutter 快速生成示例智能体，可在任意目录执行：

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
cd /tmp
python -m cookiecutter ${GIT_ROOT}/template --no-input
```

