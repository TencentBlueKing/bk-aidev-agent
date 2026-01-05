import asyncio
from logging import getLogger
import os
import json

from aidev_agent.core.extend.agent.qa import CommonQAAgent
from langchain_mcp_adapters.tools import load_mcp_tools
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()
logger = getLogger(__name__)


# MCP服务配置 - 支持从环境变量读取
def _load_mcp_config():
    """从环境变量加载MCP配置"""
    config_str = os.getenv('MCP_SERVER_CONFIG')
    if config_str:
        try:
            return json.loads(config_str)
        except json.JSONDecodeError as e:
            logger.error(f"解析 MCP_SERVER_CONFIG 环境变量失败: {e}")
            return {}
    return {}


MCP_SERVER_CONFIG = _load_mcp_config()


class CommonQAAgentExtend(CommonQAAgent):
    """扩展的智能体类，集成MCP工具"""

    @classmethod
    def _load_mcp_tools_sync(cls):
        """同步方式加载MCP工具"""
        if not hasattr(cls, '_class_mcp_tools_cache'):
            cls._class_mcp_tools_cache = []
            cls._class_mcp_tools_loaded = False

        if cls._class_mcp_tools_loaded:
            return cls._class_mcp_tools_cache

        try:
            # 确保有可用的事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = None
            except RuntimeError:
                loop = None

            if loop is None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def load_all_tools():
                all_tools = []
                for server_name, connection_config in MCP_SERVER_CONFIG.items():
                    try:
                        mcp_tools = await load_mcp_tools(
                            session=None,
                            connection=connection_config,
                            server_name=server_name
                        )
                        all_tools.extend(mcp_tools)
                    except Exception as e:
                        logger.error(f"加载MCP服务器 '{server_name}' 失败: {e}")
                return all_tools

            cls._class_mcp_tools_cache = loop.run_until_complete(load_all_tools())
            cls._class_mcp_tools_loaded = True

        except Exception as e:
            logger.error(f"加载MCP工具失败: {e}")
            cls._class_mcp_tools_cache = []

        return cls._class_mcp_tools_cache

    @classmethod
    def get_agent_executor(cls, *args, **kwargs):
        """获取智能体执行器，添加MCP工具"""
        extra_tools = kwargs.get("extra_tools", [])

        # 添加MCP工具
        try:
            mcp_tools = cls._load_mcp_tools_sync()
            extra_tools.extend(mcp_tools)
        except Exception as e:
            logger.error(f"集成MCP工具时出错: {e}")

        kwargs["extra_tools"] = extra_tools

        # 调用父类方法
        result = CommonQAAgent.get_agent_executor(*args, **kwargs)

        # 正确处理返回值（可能是元组）
        if isinstance(result, tuple) and len(result) == 2:
            executor, config = result
            return executor, config
        else:
            return result