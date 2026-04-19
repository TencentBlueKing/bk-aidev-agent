# -*- coding: utf-8 -*-
"""Plugin 测试公共 conftest。

- 强制把本仓 ``src/agent`` 注入 ``sys.path`` 最前，使 ``aidev_agent`` 解析到源码版本。
  原因：plugin 自己的 venv 通过 ``aidev-bkplugin`` 的依赖装了 wheel 版 ``aidev-agent``；
  本仓内对 ``src/agent/aidev_agent`` 的源码改动（如新增 ``ExecuteKwargs.version``）需要
  在 plugin 测试中立即可见，否则会出现"本地源码已改、wheel 未跟上"的对照失真。
- 仅影响测试时；线上/template 部署仍按各自 ``pyproject.toml`` 的依赖版本号管理。
"""

import sys
from pathlib import Path

_SRC_AGENT = Path(__file__).resolve().parents[3] / "agent"
if _SRC_AGENT.is_dir() and str(_SRC_AGENT) not in sys.path:
    sys.path.insert(0, str(_SRC_AGENT))

# 卸掉可能已被 wheel 版预加载的 aidev_agent，让后续 import 走源码。
for _mod in [name for name in list(sys.modules) if name == "aidev_agent" or name.startswith("aidev_agent.")]:
    sys.modules.pop(_mod, None)
