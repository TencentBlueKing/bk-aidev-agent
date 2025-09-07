# -*- coding: utf-8 -*-

import os
from typing import Type

from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.utils.factory import SimpleFactory
from django.conf import settings

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

agent_factory: SimpleFactory[str, Type[CommonQAAgent]] = SimpleFactory("agent")
agent_factory.register(settings.DEFAULT_AGENT, CommonQAAgent)
