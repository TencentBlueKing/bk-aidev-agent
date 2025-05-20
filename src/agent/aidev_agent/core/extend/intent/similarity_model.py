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

from typing import List, Tuple

from aidev_agent.core.utils.model_management.registry import RegistryPluginMixIn

from .utils import timeit

reg = RegistryPluginMixIn()


@timeit(message="相似度计算小模型")
def calculate_similarity(
    text_pairs: List[Tuple[str, str]],
    similarity_model_gpu_cls: str = "model.self_host.similarity_model.SimilarityModel",
) -> List[float]:
    similarity_model_gpu = reg.get_registered_object(service_name=similarity_model_gpu_cls)
    if text_pairs:
        return similarity_model_gpu.compute_similarity(text_pairs)
    else:
        return []
