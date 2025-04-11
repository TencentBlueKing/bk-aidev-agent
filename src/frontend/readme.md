# 蓝鲸AI开发者助手前端项目

本项目使用 pnpm workspace 来管理多个前端项目，包括：

- **ai-blueking**：小鲸组件库
- **web**：基于 VitePress 的文档站点

## 环境要求

- Node.js >= 20.11.1
- pnpm >= 7.0.0

## 安装

在根目录执行：

```bash
pnpm install
```

这将为所有项目安装依赖。

## 开发

### 推荐的开发方式

使用以下命令同时开发组件和文档（先构建组件库，再启动文档站点）：

```bash
pnpm start
```

### 独立开发组件库

```bash
pnpm dev:component
```

### 独立开发文档站点

```bash
pnpm dev:docs
```

## 构建

### 构建组件库

```bash
pnpm build:component
```

### 构建文档站点

```bash
pnpm build:docs
```

### 构建所有项目

```bash
pnpm build
```

## 问题排查

如果遇到模块解析错误，请尝试以下步骤：

1. 清理项目依赖和构建文件
   ```bash
   pnpm clean
   ```

2. 重新安装依赖
   ```bash
   pnpm install
   ```

3. 先构建组件库，再启动文档站点
   ```bash
   pnpm prepare:docs
   ```

## 工作区结构

项目使用 pnpm workspace 进行管理，主要配置文件：

- `pnpm-workspace.yaml`：定义了工作区包含的项目
- `package.json`：定义了顶层命令

文档项目直接引用组件库，使用 `workspace:*` 协议确保使用本地版本的组件库。

## 技术方案说明

本项目中使用了以下技术方案来解决 workspace 依赖问题：

1. 在 VitePress 配置中添加了组件库的源码路径别名
2. 使用 `optimizeDeps.exclude` 排除了组件库依赖预构建
3. 对组件库进行构建后再启动文档站点
4. 使用 `workspace:*` 协议引用本地组件包 