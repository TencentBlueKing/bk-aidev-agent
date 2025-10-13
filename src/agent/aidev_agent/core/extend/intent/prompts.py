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

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment as Environment
from langchain_core.prompts import ChatPromptTemplate

env = Environment(loader=BaseLoader)

latest_query_classification_sys_prompt_template = """现有一个智能对话系统。
我会给你一段用户和该智能对话系统的历史对话，以及当前用户的最新输入。
用户和该智能对话系统的历史对话的格式样例为：
[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
其中"HumanMessage"表示用户，"AIMessage"表示该智能对话系统。

你负责对当前用户的最新输入进行分类：
1. 如果你认为用户的这个最新输入跟历史对话信息已经完全无关，且理解该最新输入已经无需依赖历史对话信息，请只返回`<<<<<new>>>>>`

2. 如果你认为用户的这个最新输入是对历史对话的正面评价、正面反馈、正面确认等，且会话到此已经可以结束了，
   例如用户最新输入了“谢谢”、“你说得真好”等，请只返回`<<<<<finish>>>>>`

3. 其余所有情况，例如用户的这个最新输入是在接着历史对话继续进行提问或答复，或者例如完整理解这个最新输入需要依赖历史对话，
   请只返回`<<<<<continue>>>>>`

注意：
1. 举个例子，假设对话历史为：[HumanMessage(content='我的手机号xxx存在经常被无故停机的问题'), AIMessage(content='收到')]，
   假设用户当前的最新输入为“手机号yyy也是”，
   则需要依赖历史对话信息才能知道用户当前的最新输入是想询问"手机号yyy也存在经常被无故停机的问题"，因此需要返回`<<<<<continue>>>>>`
2. 再举个例子，假设对话历史为：[HumanMessage(content='广东省的省会是哪个城市'), AIMessage(content='广州')]，
   假设用户当前的最新输入为“福建呢”，则需要依赖历史对话信息才能知道用户当前的最新输入是想询问"福建省的省会是哪个城市"，
   因此需要返回`<<<<<continue>>>>>`
3. 务必确认会话到此已经可以结束了，才可以返回`<<<<<finish>>>>>`
4. 只返回`<<<<<new>>>>>`或者`<<<<<continue>>>>>`或者`<<<<<finish>>>>>`即可！永远不要返回其他任何内容！永远不要返回你的推理过程！
"""
# 请一步步思考，给出你的推理过程，最终再给出你的结论。
latest_query_classification_usr_prompt_template = env.from_string(
    """用户和该智能对话系统的对话历史如下：```{{chat_history}}```\n\n\n用户当前的最新输入如下：```{{query}}```"""
    # 在 user prompt 中重申一遍以下内容以让弱 LLM 更稳定地遵循该指令
    """\n\n\n注意：只返回`<<<<<new>>>>>`或者`<<<<<continue>>>>>`或者`<<<<<finish>>>>>`即可！"""
    """永远不要返回其他任何内容！永远不要返回你的推理过程！"""
)

query_rewrite_for_independence_sys_prompt_template = """现有一个智能对话系统。
我会给你一段用户和该智能对话系统的历史对话，以及当前用户的最新输入。
用户和该智能对话系统的历史对话的格式样例为：
[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
其中"HumanMessage"表示用户，"AIMessage"表示该智能对话系统。

你负责根据这些信息，将用户的最新输入重写成一个完全独立的query。
我会仅仅使用你重写后的query去私域知识库中检索相关文档，而不再使用历史对话！
因此，你重写后的query信息要全面、要包含所有必要的信息、完全不再依赖历史对话信息！

注意：
1. 举个例子，假设对话历史为：[HumanMessage(content='我的手机号xxx存在经常被无故停机的问题'), AIMessage(content='收到')]，
   假设用户当前的最新输入为“手机号yyy也是”，你可以返回"手机号yyy也存在经常被无故停机的问题"
2. 再举个例子，假设对话历史为：[HumanMessage(content='广东省的省会是哪个城市'), AIMessage(content='广州')]，
   假设用户当前的最新输入为“福建呢”，你可以返回"福建省的省会是哪个城市"
3. 只返回重写后的query即可！不要返回其他任何内容！返回中不要出现“用户query重写：”等表述！
"""
query_rewrite_for_independence_usr_prompt_template = env.from_string(
    """用户和该智能对话系统的对话历史如下：```{{chat_history}}```\n\n\n用户当前的最新输入如下：```{{query}}```"""
    # 在 user prompt 中重申一遍以下内容以让弱 LLM 更稳定地遵循该指令
    """\n\n\n注意：只返回重写后的query即可！不要返回其他任何内容！返回中不要出现“用户提问重写：”等表述！"""
)

gen_pseudo_tool_resource_description_sys_prompt_template = """给你一个用户query，
你负责生成一段自然语言，描述用户query的意图是什么，是想调用什么工具（可以是一个或多个）？
注意：
1. 你只需要阐述用户意图、想调用的工具即可，不要回答用户的问题！！！
2. 你的回答务必保持非常简洁！！！
3. 你的回答务必是一段自然语言描述字符串！！！"""
gen_pseudo_tool_resource_description_usr_prompt_template = env.from_string(
    """以下是提供给你的短语内容：```{{query}}```"""
)

# 将latest_query_classification、directly_respond和query_rewrite_for_independence合并（适合强模型，这样可以减少响应时间）
# NOTE: 不按照JSON格式返回的原因是需要支持stream输出，因此希望先得到标志位，然后判断标志位的情况并紧接着根据需要进行stream输出
# 比如如果判断得到标志位<<<<<finish>>>>>，则可以开启stream输出，将$RESPONSE: 后的内容在前端stream展示出来
query_cls_with_resp_or_rewrite_sys_prompt_template = """现有一个智能对话系统。
我会给你一段用户和该智能对话系统的历史对话，以及当前用户的最新输入。
用户和该智能对话系统的历史对话的格式样例为：
[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
其中"HumanMessage"表示用户，"AIMessage"表示该智能对话系统。

你负责对当前用户的最新输入进行分类：
1. 如果你认为用户的这个最新输入跟历史对话信息已经完全无关，且理解该最新输入已经无需依赖历史对话信息，
   请只返回`<<<<<new>>>>>`标志位，不要返回其他任何内容！
   返回的格式样例为：`<<<<<new>>>>>`

2. 如果你认为用户的这个最新输入是对历史对话的正面评价、正面反馈、正面确认等，且会话到此已经可以结束了，
   例如用户最新输入了“谢谢”、“你说得真好”等，
   请先返回`<<<<<finish>>>>>`标识位，然后根据历史会话和用户的最新输入，对用户的最新输入生成一个非常简洁的合理答复。
   返回的格式样例为：`<<<<<finish>>>>>$RESPONSE: 你生成的合理答复`

3. 其余情况，例如用户的这个最新输入是在接着历史对话继续进行提问或答复，
   请先返回`<<<<<continue>>>>>`标志位，然后根据历史会话和用户的最新输入，将用户的最新输入重写成一个完全独立的问题，
   要求重写后的问题信息要全面、要包含所有必要的信息、完全不再依赖历史对话信息。
   返回的格式样例为：`<<<<<continue>>>>>$REWRITTEN_QUERY: 你重写的问题`

注意：
1. 举个例子，假设在历史会话中用户提到他的手机号xxx存在经常被无故停机的问题，而用户最新输入是“手机号yyy也存在同样的问题”，
   则具体是什么问题需要根据历史对话信息才能知道，因此需要先返回`<<<<<continue>>>>>`标志位，然后根据历史信息对用户最新输入进行改写并返回。
   其中一个返回的例子为：`<<<<<continue>>>>>$REWRITTEN_QUERY: 手机号yyy也存在经常被无故停机的问题`
2. 请务必严格按照上述返回格式要求进行返回，不要生成任何额外的内容！
"""
# 请一步步思考，给出你的推理过程，最终再给出你的结论。
query_cls_with_resp_or_rewrite_usr_prompt_template = env.from_string(
    """用户和该智能对话系统的对话历史如下：```{{chat_history}}```\n\n\n用户当前的最新输入如下：```{{query}}```"""
)

sum_chat_history_for_query_sys_prompt_template = """现有一个智能对话系统。
我会给你一段用户和该智能对话系统的历史对话，以及当前用户的最新输入。
用户和该智能对话系统的历史对话的格式样例为：
[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
其中"HumanMessage"表示用户，"AIMessage"表示该智能对话系统。

你需要选择以下2种情况的其中1种进行返回。

[情况1]
如果你发现用户的最新输入存在指代省略等情况，理解其意思需要依赖历史对话中的上下文信息，请根据用户的最新输入对历史对话进行总结，
要求仅提取和总结历史对话中对理解用户的最新输入有帮助的那部分信息即可（如指代省略的内容），
要求总结后的历史对话不超过20个字。

[情况2]
如果你认为理解用户的最新输入无需依赖历史对话，请只返回None。

注意！返回内容无需说明你选择了哪种情况，直接只返回总结后的历史对话或者返回None即可，不要返回其他任何内容！
"""
sum_chat_history_for_query_usr_prompt_template = env.from_string(
    """用户和该智能对话系统的对话历史如下：```{{chat_history}}```\n\n\n用户当前的最新输入如下：```{{query}}```"""
)

# TODO: 支持多关键词提取
extract_query_keywords_sys_prompt_template = """现有一个知识库，请根据用户输入的提问，找出用户想问的问题，从问题中找出关键词，
确保可以用该关键词去知识库中通过相似度匹配得到相关文档。
注意用户提问中可能会有其他无关的内容，比如对问题的补充或其他指令，
只需要输出你认为用户要问的问题中的关键词。
只输出你认为最核心的一个关键词即可。
如果用户提问中有一些关键编码类信息，对相似度匹配可能很重要，不要遗漏了。"""
extract_query_keywords_usr_prompt_template = env.from_string("""用户提问如下：```{{query}}```""")

query_translation_sys_prompt_template = """给你一段文本，你负责判断其是中文还是英文。
1. 如果是纯中文或者中文为主，请返回None
2. 如果是纯英文或者英文为主，请将其翻译成中文后返回
永远只返回None或者翻译后的中文即可，不要返回其他任何内容！"""
query_translation_usr_prompt_template = env.from_string("""用户提问如下：```{{query}}```""")

llm_relevance_determiner_sys_prompt_template = """给你一个用户提问和一个候选文档，
你负责判断候选文档的内容是否可以回答用户提问（部分回答也可以）。
如果可以回答或者可以部分回答，请返回数字1
如果完全不可以回答，请返回数字0
永远只返回数字1或0即可，不要返回其他任何内容！
"""
llm_relevance_determiner_usr_prompt_template = env.from_string(
    """给你的候选文档如下：```{{doc}}```\n\n\n用户提问如下：```{{query}}```"""
)

llm_relevance_determiner_concate_sys_prompt_template = """给你一段历史对话内容摘要，一个用户最新提问，以及一个候选文档。
其中，历史对话内容摘要只用于帮助你理解用户最新提问的意思（当然，也可能并没有帮助，此时你可以选择直接忽略历史对话内容摘要）。
现在，你负责判断候选文档的内容是否可以回答用户最新提问。
如果可以，请返回数字1
如果不可以，请返回数字0
永远只返回数字1或0即可，不要返回其他任何内容！
"""
llm_relevance_determiner_concate_usr_prompt_template = env.from_string(
    """给你的历史对话内容摘要如下：```{{his_sum}}```\n\n\n候选文档如下：```{{doc}}```\n\n\n用户最新提问如下：```{{query}}```"""
)

llm_context_compressor_sys_prompt_template = """给你一个用户最新提问和一个候选文档，
你负责判断工具调用结果是否可以回答用户部分或全部的提问。
1. 如果可以，请根据用户最新提问对工具调用结果中可以回答用户最新提问的那部分内容进行摘要总结并返回。
要求返回的摘要言简意赅而又不丢失回答用户最新提问所需用到的信息。
2、在无法回答任何一部分问题的情况下，返回"无效的工具调用"。
记住，如果有一部分可以被回答，不能返回“无效的工具调用”！！！
直接按照上述要求返回即可，不要返回其他任何内容！

此外，为了让你可以更好地理解用户最新提问，我还会提供给你一段会话历史以供参考，格式如下：
[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
其中"HumanMessage"表示用户历史提问，"AIMessage"表示智能聊天系统的历史回答。
注意！该会话历史仅用于理解用户最新提问，且跟用户最新提问可能相关也可能不相关。
注意！你需要判断的只是候选文档内容是否可以回答用户最新提问而不是历史提问。
"""
llm_context_compressor_usr_prompt_template = env.from_string(
    "提供给你参考的会话历史内容如下：```{{provided_chat_history}}```"
    "\n\n\n给你的候选文档如下：```{{candidate_context}}```"
    "\n\n\n用户最新提问如下：```{{query}}```"
)

llm_intermediate_step_compressor_sys_prompt_template = env.from_string(
    """给你一个用户最新提问和一个 {{candidate_tool_name}} 工具的调用结果，
你负责判断工具调用结果是否可以回答用户部分或全部的提问。
1. 如果可以，请根据用户最新提问对工具调用结果中可以回答用户最新提问的那部分内容进行摘要总结并返回。
要求返回的摘要言简意赅而又不丢失回答用户最新提问所需用到的信息。
2、在无法回答任何一部分问题的情况下，返回"无效的工具调用"。
记住，如果有一部分可以被回答，不能返回“无效的工具调用”！！！
直接按照上述要求返回即可，不要返回其他任何内容！

此外，为了让你可以更好地理解用户最新提问，我还会提供给你一段会话历史以供参考，格式如下：
[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
其中"HumanMessage"表示用户历史提问，"AIMessage"表示智能聊天系统的历史回答。
注意！该会话历史仅用于理解用户最新提问，且跟用户最新提问可能相关也可能不相关。
注意！你需要判断的只是工具调用结果是否可以回答用户最新提问而不是历史提问。
"""
)
llm_intermediate_step_compressor_usr_prompt_template = env.from_string(
    "提供给你参考的会话历史内容如下：```{{provided_chat_history}}```"
    "\n\n\n给你的 {{candidate_tool_name}} 工具的调用结果如下：```{{candidate_tool_result}}```"
    "\n\n\n用户最新提问如下：```{{query}}```"
)

llm_common_compressor_sys_prompt_template = (
    "对提供给你的内容进行摘要总结，要求不能丢失关键信息。直接返回你总结后的摘要即可，不要返回其他任何内容！"
)
llm_common_compressor_usr_prompt_template = env.from_string("提供给你的内容如下：```{{content}}```")

# ####################################################################################################
# ToolCallingCommonQAAgent
# ####################################################################################################
general_qa_prompt_tool_calling = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "你是一位得力的智能问答助手。负责回答用户最新提问。"
                "{% if use_general_knowledge_on_miss %}请用通识知识回答。{% endif -%}"
                "{% if not use_general_knowledge_on_miss %}请用拒答文案'{{rejection_response}}'拒绝回答。{% endif -%}"
                "\n\n此外，跟你说下，现在是北京时间{{beijing_now}}，你如果无需用到这个北京时间信息，则忽略这个北京时间信息即可。"
            ),
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            """以下是用户最新提问内容：```{{query}}```\n\n\n{{role_prompt}}
            {% if not use_general_knowledge_on_miss %}请用拒答文案'{{rejection_response}}'拒绝回答。{% endif -%}""",
        ),
        ("placeholder", "{agent_scratchpad}"),
    ],
    template_format="jinja2",
)
private_qa_prompt_tool_calling = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "你是一位得力的智能问答助手。"
                "{% if context_type == 'private' %}"
                "我会给你提供一个用户最新提问，以及一些来自私域知识库的知识。"
                "你需要根据情况智能地选择以下3种情况的1种进行答复。"
                "\n\n1. 如果你非常自信地觉得根据给你的知识库知识可以回答给你的用户最新提问，"
                "{% elif context_type == 'qa_response' %}"
                "我会给你提供一个用户最新提问，以及一些用户的历史问答记录。"
                "你需要根据情况智能地选择以下3种情况的1种进行答复。"
                "\n\n1. 如果你非常自信地觉得根据给你的历史问答可以回答给你的用户最新提问，"
                "{% elif context_type == 'both' %}"
                "我会给你提供一个用户最新提问，以及一些来自私域知识库的知识和用户的历史问答记录。"
                "你需要根据情况智能地选择以下3种情况的1种进行答复。"
                "\n\n1. 如果你非常自信地觉得根据给你的知识库知识和历史问答可以回答给你的用户最新提问，{% endif -%}"
                "{% if context_type in ['both', 'qa_response'] %}"
                "每条历史问答记录格式如下：```json\n{\n'会话内容' : [{'role': 'user', 'content': 'xxx'}, {'role': 'assistant', 'content': 'xxx'}],"
                "\n'用户反馈评分': 5,\n'用户反馈理由': 'xxx'\n}\n```\n"
                "用户提问的部分由角色 'user' 定义，content 字段包含用户的实际提问内容。"
                "系统回答的部分由角色 'assistant' 定义，content 字段包含智能聊天系统对用户问题的回答。"
                "历史问答数据中，反馈分数越高，表明用户对该历史问答的满意程度越高。其中，1～2分表示负面反馈，是需要避免的；3分表示中性反馈；"
                "4～5分表示正面反馈，是可以酌情参考的。你需要根据用户反馈的满意程度来决定当前如何进行回答。\n"
                "注意：(1) 如果历史问答数据中涉及工具调用，你不能直接使用该历史问答数据中的工具调用结果来回答当前问题，因为工具调用"
                "返回结果通常具有时效性，历史问答数据中的工具调用结果现在不一定还生效。"
                "\n\n(2) 如果历史问答数据中用户反馈理由非空，则你还需要分析用户反馈的理由，并最终决定你需要如何返回。"
                "\n\n(3) 不要在你的返回中出现诸如“根据历史问答反馈”这样的表述，直接回答即可。{% endif -%}"
                "{% if context_type in ['both', 'private'] %}"
                "你务必严格遵循给你的知识库知识回答给你的用户最新提问。"
                "永远不要编造答案或回复一些超出该知识库知识信息范围外的答案。不要在你的返回中出现诸如“根据提供的知识库知识”这样的表述，"
                "直接回答即可。{% endif -%}"
                "\n\n2. 如果你觉得提供给你的知识库知识跟给你的用户最新提问毫无关系，而更倾向于使用提供给你的工具，请使用提供给你的工具。"
                "并根据工具返回结果进行回答。"
                "\n\n3. 如果你觉得提供给你的知识库知识和工具都不足以回答给你的用户最新提问，"
                "{% if use_general_knowledge_on_miss %}请以'根据已有知识库和工具，无法回答该问题。以下尝试根据我自身知识进行回答：'为开头，"
                "在不参考提供给你的知识库知识的前提下根据你自己的知识进行回答。"
                "！！！务必在提供给你的知识库知识和工具都不足以回答给你的用户最新提问的情况下，才可以选择本情况！！！"
                "！！！如果你选择用知识库知识或工具来回答给你的用户最新提问，"
                "就禁止使用'根据已有知识库和工具，无法回答该问题。以下尝试根据我自身知识进行回答：'作为开头！！！{% endif -%}"
                "{% if not use_general_knowledge_on_miss %}请用拒答文案'{{rejection_response}}'拒绝回答{% endif -%}"
                "\n\n注意：务必严格遵循以上要求和返回格式！请尽量保持答案简洁！请务必使用中文回答！"
                "\n\n此外，跟你说下，现在是北京时间{{beijing_now}}，你如果无需用到这个北京时间信息，则忽略这个北京时间信息即可。"
            ),
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            """{% if context_type in ['both', 'private'] %}
            以下是知识库知识内容:：```{{context}}```
            {% endif -%}  
            
            {% if context_type in ['both', 'qa_response'] %}
            以下是历史问答：```{{qa_context}}```           
            注意：
            1. 请根据用户反馈的满意度(1-5分)决定是否参考历史问答
            2. 涉及工具调用时，必须重新调用工具获取最新结果
            {% endif -%}
            
            以下是用户最新提问内容：```{{query}}```\n\n\n{{role_prompt}}""",
        ),
        ("placeholder", "{agent_scratchpad}"),
    ],
    template_format="jinja2",
)
clarifying_qa_prompt_tool_calling = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "你是一位得力的智能问答助手。"
                "{% if context_type == 'private' %}"
                "我会给你提供一个用户最新提问，以及一些来自私域知识库的知识。"
                "你需要根据情况智能地选择以下3种情况的1种进行答复。"
                "\n\n1. 如果你非常自信地觉得根据给你的知识库知识可以回答给你的用户最新提问，"
                "{% elif context_type == 'qa_response' %}"
                "我会给你提供一个用户最新提问，以及一些用户的历史问答记录。"
                "你需要根据情况智能地选择以下3种情况的1种进行答复。"
                "\n\n1. 如果你非常自信地觉得根据给你的历史问答可以回答给你的用户最新提问，"
                "{% elif context_type == 'both' %}"
                "我会给你提供一个用户最新提问，以及一些来自私域知识库的知识和用户的历史问答记录。"
                "你需要根据情况智能地选择以下3种情况的1种进行答复。"
                "\n\n1. 如果你非常自信地觉得根据给你的知识库知识和历史问答可以回答给你的用户最新提问，{% endif -%}"
                "{% if context_type in ['both', 'qa_response'] %}"
                "每条历史问答记录格式如下：```json\n{\n'会话内容' : [{'role': 'user', 'content': 'xxx'}, {'role': 'assistant', 'content': 'xxx'}],"
                "\n'用户反馈评分': 5,\n'用户反馈理由': 'xxx'\n}\n```\n"
                "用户提问的部分由角色 'user' 定义，content 字段包含用户的实际提问内容。"
                "系统回答的部分由角色 'assistant' 定义，content 字段包含智能聊天系统对用户问题的回答。"
                "历史问答数据中，反馈分数越高，表明用户对该历史问答的满意程度越高。其中，1～2分表示负面反馈，是需要避免的；3分表示中性反馈；"
                "4～5分表示正面反馈，是可以酌情参考的。你需要根据用户反馈的满意程度来决定当前如何进行回答。\n"
                "注意：(1) 如果历史问答数据中涉及工具调用，你不能直接使用该历史问答数据中的工具调用结果来回答当前问题，因为工具调用"
                "返回结果通常具有时效性，历史问答数据中的工具调用结果现在不一定还生效。"
                "\n\n(2) 如果历史问答数据中用户反馈理由非空，则你还需要分析用户反馈的理由，并最终决定你需要如何返回。"
                "\n\n(3) 不要在你的返回中出现诸如“根据历史问答反馈”这样的表述，直接回答即可。{% endif -%}"
                "{% if context_type in ['both', 'private'] %}"
                "你务必严格遵循给你的知识库知识回答给你的用户最新提问。"
                "永远不要编造答案或回复一些超出该知识库知识信息范围外的答案。不要在你的返回中出现诸如“根据提供的知识库知识”这样的表述，"
                "直接回答即可。{% endif -%}"
                "\n\n2. 如果你觉得提供给你的知识库知识跟给你的用户最新提问毫无关系，而更倾向于使用提供给你的工具，请使用提供给你的工具。"
                "并根据工具返回结果进行回答。"
                "\n\n3. 如果你觉得提供给你的知识库知识和工具都不足以回答给你的用户最新提问，"
                "{% if use_general_knowledge_on_miss %}请以'根据已有知识库和工具，无法回答该问题。以下尝试根据我自身知识进行回答：'为开头，"
                "在不参考提供给你的知识库知识的前提下根据你自己的知识进行回答。{% endif -%}"
                "{% if not use_general_knowledge_on_miss %}请用拒答文案'{{rejection_response}}'拒绝回答{% endif -%}"
                "\n\n4. 如果你觉得提供给你的知识库知识和用户最新提问是有一定联系的，"
                "只是由于用户最新提问表述模棱两可、意图不够明确导致你不知道如何回答，"
                "请尝试根据知识库知识内容对用户最新提问进行重写，以向用户二次确认其明确的意图是什么。"
                "请严格按照'抱歉，您是不是想问：\n(1) 你重写的第1个问题\n(2) 你重写的第2个问题\n'的格式进行返回，不要返回其他任何内容！"
                "该格式只是个样例，你认为提供给你的知识库知识中有多少个跟用户最新提问可能有关，你就重写多少个问题，但不要大于5个。"
                "你重写的每个问题信息都必须表述清晰、详细、意图明确，且都必须能够非常直接地用提供给你的知识库知识回答！"
                "当且仅当在用户最新提问表述模棱两可、意图不够明确，"
                "并且提供给你的知识库知识和用户最新提问是有一定联系的前提下才能选择本情况！"
                "\n\n注意：务必严格遵循以上要求和返回格式！请尽量保持答案简洁！请务必使用中文回答！"
                "此外，跟你说下，现在是北京时间{{beijing_now}}，你如果无需用到这个北京时间信息，则忽略这个北京时间信息即可。"
            ),
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            """{% if context_type in ['both', 'private'] %}
            以下是知识库知识内容:：```{{context}}```
            {% endif -%}  
            
            {% if context_type in ['both', 'qa_response'] %}
            以下是历史问答：```{{qa_context}}```           
            注意：
            1. 请根据用户反馈的满意度(1-5分)决定是否参考历史问答
            2. 涉及工具调用时，必须重新调用工具获取最新结果
            {% endif -%}
            
            以下是用户最新提问内容：```{{query}}```\n\n\n{{role_prompt}}""",
        ),
        ("placeholder", "{agent_scratchpad}"),
    ],
    template_format="jinja2",
)

# ####################################################################################################
# StructuredChatCommonQAAgent
# ####################################################################################################
general_qa_prompt_structured_chat = ChatPromptTemplate.from_messages(
    [
        (
            "human",
            """你是一个智能的决策者。我会给你以下信息：
a. 用户最新提问。
b. 一些可以让你根据需要选择使用的工具（也有可能不提供）。
c. 一些来自上述工具调用的结果。提供给你的格式是先用json说明使用的工具和传参是什么，然后在“工具调用结果：”中提供工具调用结果。
（这些工具调用结果是你在上一轮决策中认为需要调用该工具，然后工具给你返回的结果。不过，也有可能不提供）

现在，你需要根据情况智能地选择以下4种情况的1种进行输出。

[情况1]
如果你认为根据当前给定的工具调用的结果已经足够完整地回答用户所有的提问，
请在你的输出中包含一个 $JSON_BLOB 来回答用户最新提问，格式如下：
{% raw %}
\n```json
{{
  "action": "Final Answer",
  "action_input": $YOUR_ANSWER_ACCORDING_TO_CURRENT_TOOL_RESULTS
}}
```
{% endraw %}
注意！在 $YOUR_ANSWER_ACCORDING_TO_CURRENT_TOOL_RESULTS 中，
你务必严格遵循给你的工具调用结果来回答给你的用户最新提问。永远不要编造答案或回复一些超出该工具调用结果范围外的答案！回答尽量详细！
永远不要在你的回答中出现诸如'根据给定的工具调用结果'这样的字眼！直接回答用户最新提问即可！
注意！务必在根据当前给定的工具调用结果已经足够完整地回答用户所有的提问，才能选择本情况！不能偷懒直接给出答案！
注意！如果当前给定的工具调用结果信息不足以完整地回答用户所有的提问，你就一定不能选择本情况！
注意！千万不要偷懒！千万不要只部分地回答用户的提问！
注意：action_input是一个字符串，包含我们回答的全部内容。

[情况2]
如果你觉得还需要调用提供给你的工具来补充更多信息才能完整地回答用户所有的提问，
请在你的输出中包含一个 $JSON_BLOB 来指定一个工具，其中包含一个 action 键（表示工具名称）和一个 action_input 键（表示工具输入），格式如下：
{% raw %}
\n```json
{{
  "action": $TOOL_NAME,
  "action_input": $TOOL_INPUT
}}
```
{% endraw %}
注意！有效的 $TOOL_NAME 值为{{tool_names}}！
注意！有效的 $TOOL_INPUT 值请严格根据提供给你的工具定义来指定！
请看清楚工具定义，并严格遵循以下规则指定参数：
1. 必须同时指定参数名和参数值，不要只指定参数值
2. 如果工具参数定义为JSON Schema格式：
   - 必须将参数值构造为符合Schema定义的JSON对象
   - 必须将整个JSON对象作为query_param参数的值
   - 确保JSON中的字段名、类型和格式完全符合Schema定义
   - 必须包含所有required=true的字段
{% if not enable_parallel_tool_calls %}
注意！你只能使用一个工具！请你放心，如果一个工具调用结果信息还是不够，在下一轮中我还会给你机会再选择其他工具的，本轮你只需先选择一个工具即可！
{% endif %}
{% if enable_parallel_tool_calls %}
如果需要调用多个工具，且工具之间没有依赖关系，则并行调用工具，而不是串行调用工具！！
如果需要并行调用，则最终输出应该是一个包含多个工具调用的数组的$JSON_BLOB，格式如下：
{% raw %}
\n```json
[
  {
    "action": $TOOL_NAME,
    "action_input": $TOOL_INPUT
  },
  {
    "action": $TOOL_NAME,
    "action_input": $TOOL_INPUT
  },
  ...
]
```
{% endraw %}
注意：如果是并行调用多个工具的情况，则一定要按照以上格式输出！
{% endif %}
注意！只要你觉得需要调用工具补充信息才能完整回答用户最新提问，你就必须选择本情况，而不能走捷径直接选择"action": "Final Answer"的情况！
注意！不能走捷径先回答已知的问题！
注意注意再注意！对于某个你想调用的工具，你需要非常仔细地查看上下文，查看其对应的“工具调用结果：”中是否已经提供了该工具的调用结果，
如果已经提供了，就不要再重复调用该工具了！
注意注意再注意！如果你还需要调用工具补充信息才能完整回答用户最新提问，就务必选择本情况！千万不要直接就返回"Final Answer"了！

[情况3]
如果你觉得提供给你的工具无法完整回答给你的用户最新提问，
{% if use_general_knowledge_on_miss %}
请在你的输出中包含一个 $JSON_BLOB 来回答用户最新提问，格式如下：
{% raw %}
\n```json
{{
  "action": "Final Answer",
  "action_input": $YOUR_OWN_ANSWER
}}
```
{% endraw %}
注意！$YOUR_OWN_ANSWER中，对于根据提供给你的工具无法回答的内容，你需要使用你自身知识进行回应，
并且务必通过'根据我自身知识'等字眼，合理组织语言以明确清晰地让用户知道你是在用你自身的知识进行回应！
注意！$YOUR_OWN_ANSWER中不能忽略用户最新提问中的任何细节！
注意：action_input是一个字符串，包含我们回答的全部内容。
{% endif -%}
{% if not use_general_knowledge_on_miss %}
请在你的输出中包含一个 $JSON_BLOB 来拒答用户最新提问，格式如下：
{% raw %}
\n```json
{{
  "action": "Final Answer",
  "action_input": $Rejection_response
}}
``` 
{% endraw %}
注意！$Rejection_response中，请用拒答文案'{{rejection_response}}'来拒答用户最新提问！
{% endif -%}
注意！务必在提供给你的工具无法完整回答给你的用户最新提问的情况下，才可以选择本情况！

[情况4]
如果你觉得提供给你的工具应该是可以回答用户最新提问的，只是由于用户最新提问表述模棱两可、意图不够明确、信息不足导致你不知道如何调用工具，
请在你的输出中包含一个 $JSON_BLOB 来回答用户最新提问，格式如下：
{% raw %}
\n```json
{{
  "action": "Final Answer",
  "action_input": $YOUR_QUERY_CLARIFICATION
}}
```
{% endraw %}
注意！你将通过$YOUR_QUERY_CLARIFICATION向用户二次确认其明确的意图是什么。
注意！当且仅当在用户最新提问表述模棱两可、意图不够明确、信息不足，并且提供给你的工具调用结果和用户最新提问是有一定联系的前提下才能选择本情况！
注意！你需要变得更聪明一些，尽量自己揣摩用户意图即可，尽量不要选择本情况！在不必要的情况下尽量不要跟用户二次确认！

注意注意再注意！你只能选择上述4种情况中的1种进行输出！你只能返回一个 $JSON_BLOB！输出格式务必严格遵循你选择的情况中对应的格式要求！
你返回的 $JSON_BLOB 前面务必带上换行符\n以方便我用 markdown 语法对你的结果进行渲染！

此外，跟你说下，现在是北京时间{{beijing_now}}，你如果无需用到这个北京时间信息，则忽略这个北京时间信息即可。
""",
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            (
                """\n\n\n以下是你可以根据需要选择使用的工具，工具名称和参数格式为：```{{tools}}```"""
                "\n\n\n以下是用户最新提问内容：```{{query}}```"
                "\n\n\n注意注意再注意！你务必看清楚用户最新提问内容是什么！"
                "\n\n\n你的回答务必针对用户最新提问，即```{{query}}```"
                "\n\n\n再次强调，你无论如何都要以上文中定义的 $JSON_BLOB 格式输出！"
                "你返回的 $JSON_BLOB 前面务必带上换行符\n以方便我用 markdown 语法对你的结果进行渲染！"
                "\n\n\n{{role_prompt}}"
                "\n\n\n{{agent_scratchpad}}"
            ),
        ),
    ],
    template_format="jinja2",
)
# NOTE:
# https://github.com/langchain-ai/langchain/issues/3448#issuecomment-2129804159
# https://github.com/langchain-ai/langchain/issues/3448#issuecomment-2355706469
# 因此注意 structured 的 ChatPromptTemplate 需要将 agent_scratchpad 放到 human 中，
# 而不是像非 structured 的那样 ("placeholder", "{agent_scratchpad}")
private_qa_prompt_structured_chat = ChatPromptTemplate.from_messages(
    [
        (
            "human",
            """你是一个智能的决策者。我会给你以下信息：
a. 用户最新提问。
{% if context_type == 'private' %}
b. 一些来自私域知识库的知识库知识
{% elif context_type == 'qa_response' %}
b. 一些用户的历史问答记录
{% elif context_type == 'both' %}
b. 一些来自私域知识库的知识库知识和用户的历史问答记录
{% endif %}
c. 一些可以让你根据需要选择使用的工具（也有可能不提供）。
d. 一些来自上述工具调用的结果。提供给你的格式是先用json说明使用的工具和传参是什么，然后在“工具调用结果：”中提供工具调用结果。
（这些工具调用结果是你在上一轮决策中认为需要调用该工具，然后工具给你返回的结果。不过，也有可能不提供）

现在，你需要根据情况智能地选择以下4种情况的1种进行输出。

[情况1]
{% if context_type == 'private' %}
如果你认为根据当前给定的知识库知识和工具调用的结果已经足够完整地回答用户所有的提问，
{% elif context_type == 'qa_response' %}
如果你认为根据当前给定的历史问答记录和工具调用的结果已经足够完整地回答用户所有的提问，
{% elif context_type == 'both' %}
如果你认为根据当前给定的知识库知识、历史问答记录和工具调用的结果已经足够完整地回答用户所有的提问，
{% endif %}
请在你的输出中包含一个 $JSON_BLOB 来回答用户最新提问，格式如下：
{% raw %} 
\n```json
{{
  "action": "Final Answer",
  "action_input": $YOUR_ANSWER_ACCORDING_TO_CURRENT_CONTEXT
}}
```
{% endraw %}
注意！在 $YOUR_ANSWER_ACCORDING_TO_CURRENT_CONTEXT 中，
你务必严格遵循给你的上下文信息来回答给你的用户最新提问。永远不要编造答案或回复一些超出该上下文信息范围外的答案！回答尽量详细！
{% if context_type in ['both', 'qa_response'] %}
每条历史问答记录格式如下：
{% raw %} 
```json
{
  "会话内容" : [{"role": "user", "content": "xxx"}, {"role": "assistant", "content": "xxx"}],
  "用户反馈评分": 5,
  "用户反馈理由": "xxx"
}
```
{% endraw %}
用户提问的部分由角色 'user' 定义，content 字段包含用户的实际提问内容。
系统回答的部分由角色 'assistant' 定义，content 字段包含智能聊天系统对用户问题的回答。
历史问答数据中，反馈分数越高，表明用户对该历史问答的满意程度越高。其中，1～2分表示负面反馈，是需要避免的；3分表示中性反馈；4～5分表示
正面反馈，是可以酌情参考的。你需要根据用户反馈的满意程度来决定当前如何进行回答。

注意：
1. 如果历史问答数据中涉及工具调用，你不能直接使用该历史问答数据中的工具调用结果来回答当前问题，因为工具调用返回结果通常具有时效性，
历史问答数据中的工具调用结果现在不一定还生效。
2. 如果历史问答数据中用户反馈理由非空，则你还需要分析用户反馈的理由，并最终决定你需要如何返回。
3、不要在你的回答中出现诸如'根据历史问答反馈'这样的字眼！直接回答用户最新提问即可！
{% endif %}
永远不要在你的回答中出现诸如'根据给定的上下文信息'这样的字眼！直接回答用户最新提问即可！
注意！务必在根据当前给定的知识库知识和工具调用结果已经足够完整地回答用户所有的提问，才能选择本情况！不能偷懒直接给出答案！
注意！如果当前给定的信息不足以完整地回答用户所有的提问，你就一定不能选择本情况！
注意！千万不要偷懒！千万不要只部分地回答用户的提问！
注意：action_input是一个字符串，包含我们回答的全部内容。

[情况2]
如果你觉得还需要调用提供给你的工具来补充更多信息才能完整地回答用户所有的提问，
请在你的输出中包含一个 $JSON_BLOB 来指定一个工具，其中包含一个 action 键（表示工具名称）和一个 action_input 键（表示工具输入），格式如下：
{% raw %} 
\n```json
{{
  "action": $TOOL_NAME,
  "action_input": $TOOL_INPUT
}}
```
{% endraw %}
注意！有效的 $TOOL_NAME 值为{{tool_names}}！
注意！有效的 $TOOL_INPUT 值请严格根据提供给你的工具定义来指定！
请看清楚工具定义，并同时指定参数名和参数值，而不要只指定参数值。
{% if not enable_parallel_tool_calls %}
注意！你只能使用一个工具！请你放心，如果一个工具调用结果信息还是不够，在下一轮中我还会给你机会再选择其他工具的，本轮你只需先选择一个工具即可！
{% endif %}
{% if enable_parallel_tool_calls %}
如果需要调用多个工具，且工具之间没有依赖关系，则并行调用工具，而不是串行调用工具！！
如果需要并行调用，则最终输出应该是一个包含多个工具调用的数组的$JSON_BLOB，格式如下：
{% raw %}
\n```json
[
  {
    "action": $TOOL_NAME,
    "action_input": $TOOL_INPUT
  },
  {
    "action": $TOOL_NAME,
    "action_input": $TOOL_INPUT
  },
  ...
]
```
{% endraw %}
注意：如果是并行调用多个工具的情况，则一定要按照以上格式输出！
{% endif %}
注意！只要你觉得需要调用工具补充信息才能完整回答用户最新提问，你就必须选择本情况，而不能走捷径直接选择"action": "Final Answer"的情况！
注意！不能走捷径先回答已知的问题！
注意注意再注意！对于某个你想调用的工具，你需要非常仔细地查看上下文，查看其对应的“工具调用结果：”中是否已经提供了该工具的调用结果，
如果已经提供了，就不要再重复调用该工具了！
注意注意再注意！如果你还需要调用工具补充信息才能完整回答用户最新提问，就务必选择本情况！千万不要直接就返回"Final Answer"了！

[情况3]
如果你觉得提供给你的知识库知识和工具无法完整回答给你的用户最新提问，请在你的输出中包含一个 $JSON_BLOB 来回答用户最新提问，格式如下：
{% if use_general_knowledge_on_miss %}
{% raw %}
\n```json
{{
  "action": "Final Answer",
  "action_input": $YOUR_OWN_ANSWER
}}
```
{% endraw %}
注意！$YOUR_OWN_ANSWER中，对于根据提供给你的工具无法回答的内容，你需要使用你自身知识进行回应，
并且务必通过'根据我自身知识'等字眼，合理组织语言以明确清晰地让用户知道你是在用你自身的知识进行回应！
注意！$YOUR_OWN_ANSWER中不能忽略用户最新提问中的任何细节！
注意：action_input是一个字符串，包含我们回答的全部内容。
{% endif -%}
{% if not use_general_knowledge_on_miss %}
{% raw %}
\n```json
{{
  "action": "Final Answer",
  "action_input": $Rejection_response
}}
``` 
{% endraw %}
注意！$Rejection_response中，请用拒答文案'{{rejection_response}}'来拒答用户最新提问！
{% endif -%}
注意！务必在提供给你的工具无法完整回答给你的用户最新提问的情况下，才可以选择本情况！

[情况4]
如果你觉得提供给你的知识库知识和工具应该是可以回答用户最新提问的，只是由于用户最新提问表述模棱两可、意图不够明确导致你不知道如何回答，
请在你的输出中包含一个 $JSON_BLOB 来回答用户最新提问，格式如下：
{% raw %} 
\n```json
{{
  "action": "Final Answer",
  "action_input": $YOUR_QUERY_CLARIFICATION
}}
```
{% endraw %}
注意！$YOUR_QUERY_CLARIFICATION的要求：
内容上务必是严格根据当前已经提供给你的知识库知识内容或工具调用结果对用户最新提问进行重写，以向用户二次确认其明确的意图是什么。
格式上务必严格参照'抱歉，您是不是想问：\n(1) 你重写的第1个问题\n(2) 你重写的第2个问题\n'的格式，不要返回其他任何内容！"
该格式只是个样例，你认为当前已经提供给你的知识库知识或工具调用结果中有多少个跟用户最新提问可能有关，你就重写多少个问题，但不要大于5个。"
你重写的每个问题信息都必须表述清晰、详细、意图明确，
且都必须能够非常直接地用当前已经提供给你的知识库知识或工具调用结果回答，不再需要依赖额外的知识或工具调用结果！
注意！当且仅当在用户最新提问表述模棱两可、意图不够明确，并且提供给你的知识库知识或工具调用结果和用户最新提问是有一定联系的前提下才能选择本情况！
注意！你需要变得更聪明一些，尽量自己揣摩用户意图即可，尽量不要选择本情况！在不必要的情况下尽量不要跟用户二次确认！

注意注意再注意！你只能选择上述4种情况中的1种进行输出！你只能返回一个 $JSON_BLOB！输出格式务必严格遵循你选择的情况中对应的格式要求！
你返回的 $JSON_BLOB 前面务必带上换行符\n以方便我用 markdown 语法对你的结果进行渲染！

此外，跟你说下，现在是北京时间{{beijing_now}}，你如果无需用到这个北京时间信息，则忽略这个北京时间信息即可。
""",
        ),
        ("placeholder", "{chat_history}"),
        (
            "human",
            (
                "\n\n\n以下是你可以根据需要选择使用的工具：```{{tools}}```"
                "{% if context_type in ['both', 'private'] %}"
                "\n\n\n以下是知识库知识内容：```{{context}}```{% endif -%}"
                "{% if context_type in ['both', 'qa_response'] %}"
                "\n\n\n以下是历史问答内容：```{{qa_context}}```"
                "\n\n\n注意！涉及工具调用时，必须重新调用工具获取最新结果！{% endif -%}"
                "\n\n\n以下是用户最新提问内容：```{{query}}```"
                "\n\n\n注意注意再注意！你务必看清楚用户最新提问内容是什么！"
                "\n\n\n你的回答务必针对用户最新提问，即```{{query}}```"
                "\n\n\n再次强调，你无论如何都要以上文中定义的 $JSON_BLOB 格式输出！"
                "你返回的 $JSON_BLOB 前面务必带上换行符\n以方便我用 markdown 语法对你的结果进行渲染！"
                "\n\n\n{{role_prompt}}"
                "\n\n\n{{agent_scratchpad}}"
            ),
        ),
    ],
    template_format="jinja2",
)
# NOTE: 目前 structured_chat 的情况下，clarifying 和 private 使用同样的 prompt 模板即可
clarifying_qa_prompt_structured_chat = private_qa_prompt_structured_chat

intent_recognition = ChatPromptTemplate.from_messages(
    [
        (
            "human",
            """你是一个智能的决策者。我会给你一些意图选项，每项包含包含资源类别、资源ID和意图描述。
            请你根据用户的提问，选择一个或多个适合解答用户的问题的意图，输出格式必须为纯JSON数组（不要包含任何markdown标记），例如：
            [{"资源类别": "xxx","资源ID": "xxx","意图描述": "xxx"},{"资源类别": "xxx","资源ID": "xxx","意图描述": "xxx"}]
""",
        ),
        (
            "human",
            (
                "\n\n\n以下是用户最新提问内容：```{{query}}```"
                "\n\n\n注意注意再注意！你务必看清楚用户最新提问内容是什么！"
                "\n\n\n以下是意图选项内容：```{{intent_knowledge_doc}}```"
                "\n\n\n再次强调，你无论如何都要以上文中定义的json数组格式输出！"
            ),
        ),
    ],
    template_format="jinja2",
)

DEFAULT_QA_PROMPT_TEMPLATES = {k: v for k, v in globals().items() if "_qa_prompt_" in k}
DEFAULT_INTENT_RECOGNITION_PROMPT_TEMPLATES = {k: v for k, v in globals().items() if "_qa_prompt_" not in k}
