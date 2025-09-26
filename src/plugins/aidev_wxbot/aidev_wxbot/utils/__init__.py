import logging

logger = logging.getLogger(__name__)


def element_to_dict(element):
    """将 Element 对象转换为字典,并且所有key都变为小写"""
    result = {}
    for child in element:
        if child:
            # 递归处理子元素
            child_dict = element_to_dict(child)
            if child.tag.lower() in result:
                # 如果已经存在相同的标签，则将其转换为列表
                if isinstance(result[child.tag], list):
                    result[child.tag.lower()].append(child_dict)
                else:
                    result[child.tag.lower()] = [result[child.tag.lower()], child_dict]
            else:
                result[child.tag.lower()] = child_dict
        else:
            result[child.tag.lower()] = child.text
    return result


class AttrDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'AttrDict' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"'AttrDict' object has no attribute '{key}'")

    def to_dict(self):
        return self
