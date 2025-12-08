# AIDev 智能体插件开发指南

本文档将指导您完成以下内容：
1. 将【源码包部署】模式切换为【代码仓库部署】模式
2. 使用 `cruft` 管理和同步智能体插件模板
3. 智能体的二次开发与扩展

---

## 一、源码包部署 → 代码仓库部署

从 `AIDev` 创建的 AI 智能体插件默认采用**源码包部署**模式。如需改为**代码仓库部署**，请按以下步骤操作：

### 1.1 前置准备

1. 确保您已有一个可访问的 Git 仓库（如 GitHub、GitLab 或企业内部代码托管平台）
2. 从`AIDev`下载智能体源码包

### 1.2 代码提交至仓库

```bash
# 进入项目目录
cd your_project_name

# 初始化 Git 仓库（如已初始化可跳过）
git init

# 添加所有文件
git add .

# 提交代码
git commit -m "init: 初始化智能体项目"

# 添加远程仓库地址
git remote add origin <your_git_repository_url>

# 推送到远程仓库
git push -u origin main
```

### 1.3 在开发者中心切换部署模式

1. 登录 **蓝鲸开发者中心**
2. 进入目标智能体应用 → **模块配置** → **构建配置**
3. 点击「切换为代码仓库」，配置代码仓库信息，将部署模式从「源码包」切换为「代码仓库」

### 1.4 验证部署

完成配置后，进入「部署管理」页面，选择目标环境进行部署，验证代码仓库部署是否生效。

> **提示**：切换为代码仓库部署后，后续的代码更新只需推送到指定分支即可，同时也无法切换源码包部署模式。


## 二、插件模板管理

智能体插件模板由 `AIDev` 平台统一维护，您可以通过 [cruft](https://github.com/cruft/cruft) 工具关联平台模板，实现模板变更的自动同步。

### 2.1 安装 cruft

```bash
# 使用 uv（推荐）
uv add cruft --dev

# 或使用 pip
pip install cruft
```

### 2.2 关联智能体模板

在智能体项目根目录下执行：

```bash
cruft link https://github.com/TencentBlueKing/bk-aidev-agent.git \
    --directory template \
    --config-file=./support-files/cookiecutter.yaml \
    --no-input
```

**参数说明**：
- `--directory template`：指定模板所在子目录
- `--config-file`：指定 cookiecutter 配置文件路径
- `--no-input`：跳过交互式输入，使用配置文件中的默认值

### 2.3 提交关联配置

关联成功后会在项目根目录生成 `.cruft.json` 文件，请将其提交到代码仓库：

```bash
git add .cruft.json
git commit -m "chore: add cruft template link"
git push
```

### 2.4 验证模板关联

```bash
cruft check
```

如果输出 `PASSED`，则说明模板关联成功且当前代码与模板保持一致。

### 2.5 检测与同步模板更新

当平台模板发布新版本时，可通过以下命令检测并应用更新：

```bash
# 检测是否有模板更新
cruft check

# 查看更新差异并应用
cruft update
```

**交互式选项说明**：
- `v`：查看差异详情
- `y`：确认更新模板
- `n`：取消操作
- `s`：跳过本次合并

> **注意**：模板更新可能涉及配置文件或依赖变更，建议在更新前备份关键文件，更新后仔细检查差异。


## 三、二次开发

当通用智能体无法满足业务场景时，可参考以下文档扩展智能体功能：

📖 **[智能体定制开发指南](./agent/EXTENSION_AGENT.md)**

该文档涵盖：
- 智能体基础配置详解
- 自定义工具开发规范
- MCP 服务集成配置
- 完整开发示例（SRE 助手）
- 调试技巧与常见问题


## 四、获取帮助

如在开发过程中遇到问题：

1. 首先查阅 [常见问题 FAQ](./agent/FAQ.md)
2. 参考 [智能体定制开发指南](./agent/EXTENSION_AGENT.md) 
3. 在 [GitHub Issues](https://github.com/TencentBlueKing/bk-aidev-agent/issues) 提交问题

