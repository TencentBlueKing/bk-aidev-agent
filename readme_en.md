![logo.png](assets/aidev.png)

[![license](https://img.shields.io/badge/license-MIT-brightgreen.svg?style=flat)](https://github.com/TencentBlueKing/bk-aidev-agent/blob/master/LICENSE.txt)
[![Release Version](https://img.shields.io/badge/release-1.3.0-brightgreen.svg)](https://github.com/TencentBlueKing/bk-aidev-agent/releases)
[![Coverage](https://codecov.io/gh/TencentBlueKing/bk-aidev-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/TencentBlueKing/bk-aidev-agent)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/TencentBlueKing/bk-aidev-agent/pulls)


[(中文文档)](./readme.md)

## 🚀 Product Overview

BlueKing AIDev platform is dedicated to providing excellent intelligent development tool support for key stages of the development lifecycle, offering tool support for general AI business scenarios, and providing customized development extension capabilities to meet the needs of different business scenarios.

## ✨ Core Features

### AI Dolphin Intelligent Component
| Feature | Description |
|------|------|
| 💬 Intelligent Dialogue | Natural language interaction with streaming output |
| 📝 Rich Text Rendering | Markdown message parsing and display |
| 🔗 Content Reference | Document fragment referencing and context association |
| ⚡ Quick Actions | Preset commands and shortcut function support |

### Dolphin Documentation System
| Feature | Description |
|------|------|
| 📚 User Guide | Detailed tutorials from beginner to advanced |
| 🛠️ API Reference | Complete interface and type definitions |
| 💡 Example Center | Code examples for typical scenarios |
| 🔍 Interactive Demo | Operational real-time demonstration environment |
| 📜 Version Management | Clear change history records |

## 🛠️ Quick Start

### System Requirements
- Python 3.10+
- Node.js 20+
- Poetry 1.8+

### Agent Development
1. Confirm Python version (3.10.x)
    ```bash
    $ python --version
    Python 3.10.5
   ```

2. Install `poetry`: Poetry should be installed in a separate environment to avoid interference with the project environment
   ```shell
   curl -sSL https://install.python-poetry.org | python3 - --version 1.8.5
   ```

3. Initialize the project environment (virtual environment located in the project root directory `.venv`), this step will initialize the local `pre-commit` component
   ```shell
   $ make
   ```

### Frontend Development
#### Component Development
```bash
cd src/frontend
pnpm install
pnpm dev:component  # Development mode (AI Dolphin component)
pnpm build:component  # Production build (AI Dolphin component)
```

#### Vue2 Component Testing
```bash
cd src/frontend
pnpm install
cd vue2-playground
pnpm run serve  # Start Vue2 environment testing
```

#### Documentation Development
```bash
cd src/frontend
pnpm install
pnpm dev:docs  # Development mode (http://localhost:5173)
pnpm build:docs  # Production build
```

### Development Recommendations
1. Execute code check before submission:
```bash
cd src/frontend/ai-blueking
pnpm prettier
```
2. Recommended development tools:
- VS Code + Volar extension
- ESLint + Prettier
- Chrome Developer Tools

## 📂 Project Structure
```
bk-aidev-agent/
├── src/
│   ├── agent/            # Backend Agent service
│   └── frontend/         # Frontend project
│       ├── ai-blueking/  # AI Dolphin component
│       │   ├── src/      # Component source code
│       │   ├── playground/ # Local development environment
│       │   └── scripts/  # Build scripts
│       ├── vue2-playground/ # Vue2 environment testing project
│       │   ├── src/      # Vue2 test application source code
│       │   └── public/   # Static resources
│       └── web/          # Documentation site
│           ├── docs/     # Documentation content
│           └── server.cjs # Documentation server
├── docs/                 # Design documents
├── scripts/              # Build scripts
└── tests/                # Test cases
```

## 📚 Related Resources
- [Dolphin Component API Documentation](src/frontend/web/docs/api/props.md)
- [Dolphin Component Changelog](src/frontend/ai-blueking/CHANGELOG.md)
- [Dolphin Component FAQ](src/frontend/web/docs/faq.md)

## 💬 Community Support
- [BlueKing Forum](https://bk.tencent.com/s-mart/community)
- [BlueKing DevOps Online Video Tutorials](https://bk.tencent.com/s-mart/video/)
- [BlueKing Community Edition Exchange Group](https://jq.qq.com/?_wv=1027&k=5zk8F7G)

## 🌐 BlueKing Open Source Ecosystem
| Project | Description |
|------|------|
| [BK-CMDB](https://github.com/Tencent/bk-cmdb) | Enterprise Configuration Management Platform |
| [BK-CI](https://github.com/Tencent/bk-ci) | Continuous Integration and Delivery System |
| [BK-BCS](https://github.com/Tencent/bk-bcs) | Container Management Service Platform |
| [BK-PaaS](https://github.com/Tencent/bk-paas) | SaaS Application Development Platform |
| [BK-SOPS](https://github.com/Tencent/bk-sops) | Standard Operation and Maintenance Scheduling System |
| [BK-JOB](https://github.com/Tencent/bk-job) | Job Script Management System |

## 🤝 Contributing
We welcome all forms of contributions! If you have good opinions or suggestions, welcome to give us Issues or Pull Requests to contribute to the BlueKing open source community.

1. Fork the project repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit your changes (`git commit -m 'feat: add some feature'`)
4. Push to the branch (`git push origin feat/your-feature`)
5. Create a Pull Request

The [Tencent Open Source Incentive Plan](https://opensource.tencent.com/contribution) encourages developer participation and contribution. Looking forward to your joining.

## 📜 License
This project is open-sourced under the [MIT License](./LICENSE.txt) 