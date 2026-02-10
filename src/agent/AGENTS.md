# AGENTS.md - 项目规则指南

## 项目概述

`aidev-agent` 是一个基于 uv 管理的智能体sdk代码

## 使用指南

### 测试运行
```bash
make test path=xxx
```
> ⚠️ 注意：请勿直接使用 `pytest` 命令运行测试

### 代码提交流程
1. 完成任务后执行 `git commit` 保存变更
2. 提交信息必须遵循以下格式：
   - 格式示例：`feat: add a new feature` 或 `fix: fix a bug`
   - 所有提交信息必须以 "committed by AI assistant" 结尾

## 单元测试规范

1. **参数化测试**：优先使用参数化单元测试，减少重复代码
   ```python
   @pytest.mark.parametrize("input_data, expected", [
       (data1, expected1),
       (data2, expected2),
   ])
   def test_function(input_data, expected):
       # 测试代码
   ```
2. **代码简洁性**：单元测试函数不得超过 30 行
3. **测试范围**：仅覆盖核心逻辑，测试生成 1-2 个实例即可
4. **代码组织**：
 - 单测目录：与源码目录保持一致
 - 命名规则 Test{类名}、test_{方法名}
5. **mock**
 - 使用`baker.make` mock 数据记录
 - 通用的 mock 使用 conftest.py 进行管理
 - 如果是数据仅在测试类中应用，则只在类中进行 mock
