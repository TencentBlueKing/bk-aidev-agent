import logging
from dataclasses import dataclass
from typing import Callable, Dict, Generic, Optional, TypeVar, cast

logger = logging.getLogger(__name__)


class Teapot:
    def __init__(self, factory: "GenericFactory"):
        self.__factory = factory

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        factory = self.__factory
        raise NotImplementedError(f"I'm a teapot from factory {factory.name}, I don't have {name}")


T_Type = TypeVar("T_Type")
T_Value = TypeVar("T_Value")
T_Instance = TypeVar("T_Instance")


@dataclass
class FactoryItem(Generic[T_Value]):
    priority: int
    value: T_Value


class GenericFactory(Generic[T_Type, T_Value]):
    """
    通用泛型工厂实现

    >>> class MockType(Enum):
    ...     Registered = "A"
    ...     NotRegister = "B"

    >>> factory: Factory[MockType, str] = Factory("testing", "")
    """

    factory_type = "generic"

    def __init__(self, name: str, defaults: Optional[T_Value] = None, allow_overwrite: bool = True):
        self.values: Dict[Optional[T_Type], FactoryItem[T_Value]] = {}
        self.allow_overwrite = allow_overwrite
        self.name = name

        if defaults is None:
            self.defaults = cast(T_Value, Teapot(self))
        else:
            self.defaults = defaults

    def replace_defaults(self, defaults: T_Value) -> T_Value:
        """
        替换默认值，返回旧值
        """

        if not self.allow_overwrite:
            raise RuntimeError(f"default value of {self.factory_type} factory {self.name} already exists")

        logger.info("replace defaults of %s factory %s", self.factory_type, self.name)

        legacy_instance = self.defaults
        self.defaults = defaults
        return legacy_instance

    def _post_register(self, typ: T_Type, value: T_Value, priority: int):
        """注册后回调"""

    def register(self, typ: T_Type, value: T_Value, priority: int = 0):
        """
        注册类型，优先级高的类型会覆盖优先级低的类型

        :raises RuntimeError: 如果类型已经注册，且不允许覆盖
        """

        registered = self.values.get(typ)

        if registered and not self.allow_overwrite:
            raise RuntimeError(f"{typ} of {self.factory_type} factory {self.name} already exists")

        if registered and priority < registered.priority:
            logger.info(
                "skip register %s of %s factory %s, because priority is %s, lower than %s",
                typ,
                self.factory_type,
                self.name,
                priority,
                registered.priority,
            )
            return

        logger.info("register %s of %s factory %s", typ, self.factory_type, self.name)
        self.values[typ] = FactoryItem(priority=priority, value=value)
        self._post_register(typ, value, priority)

    def get(self, typ: Optional[T_Type] = None) -> T_Value:
        """获取指定类型的值，如果不存在则返回默认值"""
        registered = self.values.get(typ)
        if not registered:
            return self.defaults

        return registered.value

    def must_get(self, typ: T_Type) -> T_Value:
        """
        获取指定类型的值，如果不存在则抛出异常

        :raises RuntimeError: 如果未注册
        """

        if typ not in self.values:
            raise RuntimeError(f"{typ} of {self.factory_type} factory {self.name} not exists")

        return self.values[typ].value

    def remove(self, typ: T_Type) -> None:
        registered = self.values.get(typ)
        if not registered:
            return
        del self.values[typ]

    def clear(self):
        """清空注册的类型"""

        logger.warning("%s factory %s cleared", self.factory_type, self.name)
        self.values.clear()

    def __getitem__(self, key: T_Type) -> T_Value:
        """按下标获取类型的值，相当于 self.must_get(key)"""
        return self.must_get(key)

    def __contains__(self, typ: T_Type) -> bool:
        """是否支持该类型"""

        return typ in self.values

    def __iter__(self):
        """遍历已注册的类型"""
        return iter(self.values)

    def __len__(self):
        """返回已注册的类型数量"""
        return len(self.values)

    def keys(self):
        """返回已注册类型的键"""
        return self.values.keys()

    def registers(self):
        """返回已注册类型的值"""
        return (i.value for i in self.values.values())

    def items(self):
        """返回已注册的类型的键和值"""
        return ((k, i.value) for k, i in self.values.items())


class SingletonFactory(Generic[T_Type, T_Instance], GenericFactory[T_Type, T_Instance]):
    """实例工厂类，用于注册已经初始化的实例对象"""

    factory_type = "singleton"

    def __call__(self, typ: Optional[T_Type] = None) -> T_Instance:
        """获取指定类型的实例，相当于 self.get(typ)"""
        return self.get(typ)


class SimpleFactory(Generic[T_Type, T_Instance], GenericFactory[T_Type, Callable[..., T_Instance]]):
    """简单工厂类，用于注册创建实例的回调函数"""

    factory_type = "simple"

    def make(self, typ: T_Type, *args, **kwargs) -> T_Instance:
        """构造对应类型的实例"""

        return self(typ, *args, **kwargs)

    def must_make(self, typ: T_Type, *args, **kwargs) -> T_Instance:
        """构造对应类型的实例，如果不存在则抛出异常"""

        callback = self.must_get(typ)

        return callback(*args, **kwargs)

    def __call__(self, typ: Optional[T_Type] = None, *args, **kwargs) -> T_Instance:
        """构造对应类型的实例"""

        callback = self.get(typ)

        return callback(*args, **kwargs)
