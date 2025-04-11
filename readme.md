![logo.png](assets/aidev.png)

[![license](https://img.shields.io/badge/license-MIT-brightgreen.svg?style=flat)](https://github.com/TencentBlueKing/bk-aidev-agent/blob/master/LICENSE.txt)
[![Release Version](https://img.shields.io/badge/release-1.3.0-brightgreen.svg)](https://github.com/TencentBlueKing/bk-aidev-agent/releases)
[![Coverage](https://codecov.io/gh/TencentBlueKing/bk-aidev-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/TencentBlueKing/bk-aidev-agent)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/TencentBlueKing/bk-aidev-agent/pulls)

[(English Documents Available)](./readme_en.md)

> 重要提示: 分支在开发过程中可能处于不稳定或者不可用状态，请通过 [Releases](https://github.com/TencentBlueKing/bk-aidev-agent/releases) 获取稳定的二进制文件

## Overview

蓝鲸 AIDev 平台致力于为研发生命周期的关键阶段提供卓越的智能研发工具支持，为业务通用AI场景提供工具支持，为满足不同业务场景需求提供自定义开发扩展能力

## Features


## Roadmap

## Quickstart
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
4. 项目结构
	```
	src # 项目源码
	├── agent         # aidev agent sdk
	├── frontend      # 前端目录
	│   ├── ai-blueking  # 小鲸组件
	│   ├── web          # 小鲸文档 Web 应用
   ```

## Support

- [蓝鲸论坛](https://bk.tencent.com/s-mart/community)
- [蓝鲸 DevOps 在线视频教程](https://bk.tencent.com/s-mart/video/)
- [蓝鲸社区版交流群](https://jq.qq.com/?_wv=1027&k=5zk8F7G)

## BlueKing Community

- [BK-CMDB](https://github.com/Tencent/bk-cmdb)：蓝鲸配置平台（蓝鲸 CMDB）是一个面向资产及应用的企业级配置管理平台。
- [BK-CI](https://github.com/Tencent/bk-ci)：蓝鲸持续集成平台是一个开源的持续集成和持续交付系统，可以轻松将你的研发流程呈现到你面前。
- [BK-BCS](https://github.com/Tencent/bk-bcs)：蓝鲸容器管理平台是以容器技术为基础，为微服务业务提供编排管理的基础服务平台。
- [BK-PaaS](https://github.com/Tencent/bk-paas)：蓝鲸 PaaS 平台是一个开放式的开发平台，让开发者可以方便快捷地创建、开发、部署和管理 SaaS 应用。
- [BK-SOPS](https://github.com/Tencent/bk-sops)：标准运维（SOPS）是通过可视化的图形界面进行任务流程编排和执行的系统，是蓝鲸体系中一款轻量级的调度编排类 SaaS 产品。
- [BK-JOB](https://github.com/Tencent/bk-job) 蓝鲸作业平台(Job)是一套运维脚本管理系统，具备海量任务并发处理能力。

## Contributing

如果你有好的意见或建议，欢迎给我们提 Issues 或 Pull Requests，为蓝鲸开源社区贡献力量。   
[腾讯开源激励计划](https://opensource.tencent.com/contribution) 鼓励开发者的参与和贡献，期待你的加入。

## License

基于 MIT 协议， 详细请参考 [LICENSE](./LICENSE.txt)