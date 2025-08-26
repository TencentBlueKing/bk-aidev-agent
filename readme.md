![logo.png](assets/aidev.png)

[![license](https://img.shields.io/badge/license-MIT-brightgreen.svg?style=flat)](https://github.com/TencentBlueKing/bk-aidev-agent/blob/master/LICENSE.txt)
[![Release Version](https://img.shields.io/badge/release-1.3.0-brightgreen.svg)](https://github.com/TencentBlueKing/bk-aidev-agent/releases)
[![Coverage](https://codecov.io/gh/TencentBlueKing/bk-aidev-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/TencentBlueKing/bk-aidev-agent)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/TencentBlueKing/bk-aidev-agent/pulls)


[(English Documents Available)](./readme_en.md)

## 🚀 产品概述

蓝鲸 AIDev 平台致力于为研发生命周期的关键阶段提供卓越的智能研发工具支持，为业务通用AI场景提供工具支持，为满足不同业务场景需求提供自定义开发扩展能力



## ✨ 核心特性

### AI 小鲸智能组件
| 功能 | 描述 |
|------|------|
| 💬 智能对话 | 支持流式输出的自然语言交互 |
| 📝 富文本渲染 | Markdown 消息解析与展示 |
| 🔗 内容引用 | 文档片段引用与上下文关联 |
| ⚡ 快捷操作 | 预设指令与快捷功能支持 |

### 小鲸文档系统
| 功能 | 描述 |
|------|------|
| 📚 使用指南 | 从入门到精通的详细教程 |
| 🛠️ API 参考 | 完整的接口与类型定义 |
| 💡 示例中心 | 典型场景的代码示例 |
| 🔍 交互演示 | 可操作的实时演示环境 |
| 📜 版本管理 | 清晰的变更历史记录 |


## 🛠️ 快速开始

### 系统要求
- Python 3.10+
- Node.js 20+
- Poetry 1.8+

### Agent 开发
1. 确认 Python 版本（3.10.x）
    ```bash
    $ python --version
    Python 3.10.5
   ```

2. 安装 `poetry`：Poetry 应该安装一个独立的环境，避免与项目环境互相影响
   ```shell
   curl -sSL https://install.python-poetry.org | python3 - --version 1.8.5
   ```

3. 初始化项目环境（虚拟环境位于项目根目录 `.venv` 下），此步骤将始化本地`pre-commit`组件
   ```shell
   $ make
   ```

### 前端开发
#### 组件开发
```bash
cd src/frontend
pnpm install
pnpm dev:component  # 开发模式（AI小鲸组件）
pnpm build:component  # 生产构建（AI小鲸组件）
```

#### Vue2 组件测试
```bash
cd src/frontend
pnpm install
cd vue2-playground
pnpm run serve  # 启动 Vue2 环境测试
```

#### 文档开发
```bash
cd src/frontend
pnpm install
pnpm dev:docs  # 开发模式 (http://localhost:5173)
pnpm build:docs  # 生产构建
```

### 开发建议
1. 提交前请执行代码检查：
```bash
cd src/frontend/ai-blueking
pnpm prettier
```
2. 推荐开发工具：
- VS Code + Volar 扩展
- ESLint + Prettier
- Chrome 开发者工具

## 📂 项目结构
```
bk-aidev-agent/
├── src/
│   ├── agent/            # 后端 Agent SDK
│   └── frontend/         # 前端项目
│       ├── ai-blueking/  # AI 小鲸组件
│       │   ├── src/      # 组件源代码
│       │   ├── playground/ # 本地开发环境
│       │   └── scripts/  # 构建脚本
│       ├── vue2-playground/ # Vue2 环境测试工程
│       │   ├── src/      # Vue2 测试应用源码
│       │   └── public/   # 静态资源
│       └── web/          # 文档站点
│           ├── docs/     # 文档内容
│           └── server.cjs # 文档服务器
├── templates/            # Agent模板
├── docs/                 # 设计文档
├── scripts/              # 构建脚本
└── tests/                # 测试用例
```

## 📚 相关资源
- [小鲸组件 API 文档](src/frontend/web/docs/api/props.md)
- [小鲸组件变更日志](src/frontend/ai-blueking/CHANGELOG.md)
- [小鲸组件常见问题](src/frontend/web/docs/faq.md)

## 💬 社区支持
- [蓝鲸论坛](https://bk.tencent.com/s-mart/community)
- [蓝鲸 DevOps 在线视频教程](https://bk.tencent.com/s-mart/video/)
- [蓝鲸社区版交流群](https://jq.qq.com/?_wv=1027&k=5zk8F7G)

## 🌐 蓝鲸开源生态
| 项目 | 描述 |
|------|------|
| [BK-CMDB](https://github.com/Tencent/bk-cmdb) | 企业级配置管理平台 |
| [BK-CI](https://github.com/Tencent/bk-ci) | 持续集成与交付系统 |
| [BK-BCS](https://github.com/Tencent/bk-bcs) | 容器管理服务平台 |
| [BK-PaaS](https://github.com/Tencent/bk-paas) | SaaS 应用开发平台 |
| [BK-SOPS](https://github.com/Tencent/bk-sops) | 标准运维调度系统 |
| [BK-JOB](https://github.com/Tencent/bk-job) | 作业脚本管理系统 |

## 🤝 参与贡献
我们欢迎各种形式的贡献！如果你有好的意见或建议，欢迎给我们提 Issues 或 Pull Requests，为蓝鲸开源社区贡献力量。

1. Fork 项目仓库
2. 创建特性分支 (`git checkout -b feat/your-feature`)
3. 提交更改 (`git commit -m 'feat: add some feature'`)
4. 推送到分支 (`git push origin feat/your-feature`)
5. 创建 Pull Request

[腾讯开源激励计划](https://opensource.tencent.com/contribution) 鼓励开发者的参与和贡献，期待你的加入。

## 📜 开源协议
本项目采用 [MIT 协议](./LICENSE.txt) 开源
