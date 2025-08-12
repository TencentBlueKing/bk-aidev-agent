from abc import ABC, abstractmethod
from typing import Any, Dict

from langchain_core.tools import StructuredTool


class AbstractBKAidevResourceManager(ABC):
    """
    Abstract base class for BkAidev Resource Manager.
    Defines all API methods as abstract methods to allow custom implementations.
    """

    @abstractmethod
    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict:
        """Retrieve knowledgebase by ID"""

    @abstractmethod
    def retrieve_knowledge(self, id: int, **kwargs) -> dict:
        """Retrieve knowledge by ID"""

    @abstractmethod
    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]:
        """Get chat session context"""

    @abstractmethod
    def retrieve_agent_config(self, agent_code: str, **kwargs) -> dict:
        """Retrieve agent config by agent code"""

    @abstractmethod
    def construct_tool(self, tool_code: str, **kwargs) -> StructuredTool:
        """Construct tool from tool code"""

    @abstractmethod
    def knowledge_query(self, data: Dict[str, Any]) -> dict:
        """Perform knowledge query"""
