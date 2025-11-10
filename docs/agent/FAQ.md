# AIDev 智能体开发常见问题

## 本地环境部署

<hr/>

### ❓问题：no such table: account_user
```text
OperationalError at /
no such table: account_user
```
### 🔍 原因
数据库未完成初始化，缺少必要的数据表结构。

### ✅ 解决方案
执行以下命令完成数据库迁移：
```shell
source .env
source .venv/bin/activate
python bin/manage.py migrate
```

<hr/>

### ❓问题：智能体关联失败
使用智能体(ai-xxx)前，需要先将其关联至 [AI 开发助手] 空间

### 🔍 原因
如果您是直接从开发者中心创建的 AI 智能体插件，在使用前必须先将其关联到特定的项目空间。

### ✅ 解决方案
1. 选择或创建一个智能体专属的项目空间

<img src="./assets/create_space.png" width="400px"/>

2. 将智能体绑定至项目空间（注意：从开发者中心创建的智能体只能关联到原先指定的空间）

<img src="./assets/bind_space.png" width="60%"/>

3. 完成关联后，请务必配置并发布智能体

<img src="./assets/publish_agent.png" width="60%"/>

<hr/>

### ❓问题：no such table: my_cache_table

### 🔍 原因
本地环境中缺少 Django 缓存所需的数据表。

### ✅ 解决方案
执行以下命令创建缓存表：
```shell
source .env
source .venv/bin/activate
python bin/manage.py createcachetable
```

<hr/>

### ❓问题：智能体发布失败

在聊天窗口会话时出现提示：请配置并发布智能体待使用的LLM模型  

<img src="./assets/agent_llm_empty.png" width="60%"/>

### 🔍 原因
智能体尚未完成发布流程，或者未配置所需的本地模型。

### ✅ 解决方案
请完成智能体的配置并执行发布操作：

<img src="./assets/publish_agent.png" width="60%"/>