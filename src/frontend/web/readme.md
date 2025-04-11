# AI 小鲸文档项目

<p align="center">
  <img src="./docs/public/ai-logo.svg" alt="AI 小鲸" width="128" height="128">
</p>

<p align="center">
  <a href="https://github.com/blueking/ai-blueking"><img src="https://img.shields.io/badge/版本-0.5.2-blue" alt="版本"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-green" alt="许可证"></a>
</p>

## 简介

这是 AI 小鲸智能对话组件的官方文档项目，使用 VitePress 构建。本项目包含了 AI 小鲸组件的使用文档、API 参考和示例代码。

## 项目启动

### 安装依赖

```bash
# npm
npm install

# yarn
yarn install

# pnpm
pnpm install
```

### 本地开发

```bash
# 启动开发服务器
npm run dev
```

### 构建文档

```bash
# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

## 项目结构

```
.
├── .vitepress/        # VitePress 配置目录
│   ├── config.js      # 站点配置文件
│   └── theme/         # 主题自定义
├── src/               # 文档源文件
│   ├── api/           # API 文档
│   ├── guide/         # 使用指南
│   ├── demos/         # 示例代码
│   ├── public/        # 静态资源
│   └── index.md       # 首页
├── package.json       # 项目依赖
└── README.md          # 项目说明
```

## 文档内容

- **指南**：组件介绍、快速开始、核心功能、高级用法等
- **API 文档**：组件属性、事件、方法等详细说明
- **示例**：各种使用场景的示例代码
- **更新日志**：版本更新记录
- **常见问题**：使用过程中的常见问题解答

## 贡献指南

如需为文档做贡献，请遵循以下步骤：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

## 许可证

[MIT 许可证](../../../LICENSE.txt) 