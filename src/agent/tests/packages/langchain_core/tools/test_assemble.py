# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from types import SimpleNamespace

from aidev_agent.packages.langchain_core.tools.assemble import assemble_bound_tools


def test_assemble_bound_tools_keeps_first_named_duplicate(caplog):
    first = SimpleNamespace(name="Node_ListNode", metadata={"mcp_name": "bcs-api-gateway-mcp-resource"})
    second = SimpleNamespace(name="Node_ListNode", metadata={"mcp_name": "bcs-api-gateway-mcp-cluster"})
    other = SimpleNamespace(name="GetCluster", metadata={"mcp_name": "bcs-api-gateway-mcp-cluster"})

    with caplog.at_level("WARNING"):
        assembled = assemble_bound_tools([first, other, second])

    assert assembled == [first, other]
    assert "name=Node_ListNode" in caplog.text
    assert "keep_source=bcs-api-gateway-mcp-resource" in caplog.text
    assert "drop_source=bcs-api-gateway-mcp-cluster" in caplog.text


def test_assemble_bound_tools_keeps_nameless_tools():
    named = SimpleNamespace(name="weather", metadata={"tool_code": "weather"})
    nameless = SimpleNamespace(name="", metadata={})
    missing = SimpleNamespace(metadata={})

    assembled = assemble_bound_tools([named, nameless, missing, named])

    assert assembled == [named, nameless, missing]


def test_assemble_bound_tools_accepts_dict_tools_and_empty_input():
    first = {"name": "search", "metadata": {"tool_code": "platform-search"}}
    second = {"name": "search", "mcp_name": "mcp-search"}

    assert assemble_bound_tools([first, second]) == [first]
    assert assemble_bound_tools(None) == []
    assert assemble_bound_tools([]) == []
