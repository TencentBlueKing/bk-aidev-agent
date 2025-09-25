# -*- coding: utf-8 -*-

import os
from typing import Type

from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.services.config_manager import AgentConfigManager
from aidev_agent.utils.factory import SimpleFactory

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

agent_factory: SimpleFactory[str, Type[CommonQAAgent]] = SimpleFactory("agent")
agent_config_factory: SimpleFactory[str, Type[AgentConfigManager]] = SimpleFactory("config_manager")
