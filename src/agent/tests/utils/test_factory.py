from enum import Enum

import pytest
from aidev_agent.utils.factory import GenericFactory, SimpleFactory, SingletonFactory

from tests._typing import FixtureType as ft


class MockType(Enum):
    Registered = "A"
    NotRegister = "B"


class TestGenericFactory:
    """测试 GenericFactory"""

    factory: GenericFactory[MockType, str]

    @pytest.fixture(autouse=True)
    def setup(self, faker: ft.faker):
        self.default_value = faker.word()
        self.registered_value = faker.word()

        self.factory = GenericFactory("testing", self.default_value)
        self.factory.register(MockType.Registered, self.registered_value)

    def test_without_defaults(self):
        """测试不传入默认值"""
        factory: GenericFactory[MockType, str] = GenericFactory("testing")

        with pytest.raises(NotImplementedError):
            factory.defaults.startswith("not-implemented!")

    def test_factory_type(self):
        """测试 factory_type 默认值"""

        assert self.factory.factory_type == "generic"

    def test_allow_overwrite(self):
        """测试 allow_overwrite 默认值"""

        assert self.factory.allow_overwrite is True

    def test_replace_defaults_allow_overwrite(self):
        """测试替换默认值"""

        self.factory.allow_overwrite = True

        default_value = "b"
        assert self.factory.replace_defaults(default_value) == self.default_value
        assert self.factory.get(MockType.NotRegister) == default_value

    def test_replace_defaults_overwrite(self):
        """测试不允许覆盖时替换默认值"""

        self.factory.allow_overwrite = False

        with pytest.raises(RuntimeError):
            self.factory.replace_defaults("u-raise-me-up")

    def test_register(self):
        """测试注册"""

        assert MockType.NotRegister not in self.factory

        self.factory.register(MockType.NotRegister, "b")

        assert MockType.NotRegister in self.factory

    def test_register_overwrite(self):
        """测试注册不允许覆盖"""

        self.factory.allow_overwrite = False

        with pytest.raises(RuntimeError):
            self.factory.register(MockType.Registered, "b")

    def test_register_allow_overwrite(self):
        """测试注册时允许覆盖"""

        self.factory.allow_overwrite = True

        self.factory.register(MockType.Registered, "b")

    def test_register_not_overwrite_because_of_priority(self):
        """测试因为优先级导致无法覆盖注册"""

        self.factory.register(MockType.Registered, "a", priority=1)
        self.factory.register(MockType.Registered, "b", priority=0)

        assert self.factory.get(MockType.Registered) == "a"

    def test_register_overwrite_because_of_priority(self):
        """测试优先级覆盖注册"""

        self.factory.register(MockType.Registered, "a", priority=0)
        self.factory.register(MockType.Registered, "b", priority=1)

        assert self.factory.get(MockType.Registered) == "b"

    def test_post_register(self):
        """测试注册后回调"""

        callbacks = {}

        class MockFactory(GenericFactory[MockType, str]):
            def _post_register(self, typ: MockType, value: str, priority: int):
                callbacks[typ] = value

        factory = MockFactory("testing")
        factory.register(MockType.Registered, "1")
        factory.register(MockType.NotRegister, "2")

        assert callbacks[MockType.Registered] == "1"
        assert callbacks[MockType.NotRegister] == "2"

    def test_get_unsupported_type(self):
        """测试获取不支持的值，返回默认值"""

        assert self.factory.get(MockType.NotRegister) == self.default_value

    def test_get_supported_type(self):
        """测试获取支持的值"""
        assert self.factory.get(MockType.Registered) == self.registered_value

    def test_get_none(self):
        """测试获取默认值"""
        assert self.factory.get() == self.default_value

    def test_must_get_unsupported_type(self):
        """测试获取不支持的值，抛出异常"""

        with pytest.raises(RuntimeError):
            self.factory.must_get(MockType.NotRegister)

    def test_must_get_supported_type(self):
        """测试获取支持的值"""
        assert self.factory.must_get(MockType.Registered) == self.registered_value

    def test_contains(self):
        """测试是否支持该类型"""

        assert MockType.Registered in self.factory
        assert MockType.NotRegister not in self.factory

    def test_clear(self):
        """测试清空注册的值"""

        assert MockType.Registered in self.factory

        self.factory.clear()

        assert MockType.Registered not in self.factory

    def test_getitem_unsupported_type(self):
        """测试获取不支持的值，抛出异常"""

        with pytest.raises(RuntimeError):
            self.factory[MockType.NotRegister]

    def test_getitem_supported_type(self):
        """测试获取支持的值"""

        assert self.factory[MockType.Registered] == self.registered_value

    def test_iter(self):
        """遍历已注册的类型"""

        registered_types = set(self.factory)

        assert MockType.Registered in registered_types
        assert MockType.NotRegister not in registered_types

    def test_len(self):
        """测试长度"""

        assert len(self.factory) == 1

        self.factory.register(MockType.NotRegister, "b")

        assert len(self.factory) == 2

    def test_keys(self):
        """测试注册的类型的键"""

        keys = self.factory.keys()
        assert MockType.Registered in keys
        assert MockType.NotRegister not in keys

    def test_registers(self):
        """测试注册的类型的值"""

        registers = self.factory.registers()
        assert self.registered_value in registers

    def test_items(self):
        """测试已注册的类型的键和值"""

        items = self.factory.items()
        assert (MockType.Registered, self.registered_value) in items


class TestSingletonFactory:
    """测试 SingletonFactory"""

    factory: SingletonFactory[MockType, str]

    @pytest.fixture(autouse=True)
    def setup(self, faker: ft.faker):
        self.default_value = faker.word()
        self.registered_value = faker.word()

        self.factory = SingletonFactory("testing", self.default_value)
        self.factory.register(MockType.Registered, self.registered_value)

    def test_factory_type(self):
        """测试 factory_type 默认值"""

        assert SingletonFactory.factory_type == "singleton"

    def test_call_without_args(self):
        """测试不传入参数时，返回默认值"""

        assert self.factory() == self.default_value

    def test_call_with_supported_type(self):
        """测试传入支持的类型时，返回对应值"""

        assert self.factory(MockType.Registered) == self.registered_value

    def test_call_with_unsupported_type(self):
        """测试传入不支持的类型时，返回默认值"""

        assert self.factory(MockType.NotRegister) == self.default_value


class TestSimpleFactory:
    """测试 SimpleFactory"""

    factory: SimpleFactory[MockType, str]

    @pytest.fixture(autouse=True)
    def setup(self, faker: ft.faker, mocker: ft.mocker):
        self.default_value = faker.word()
        self.registered_value = faker.word()

        self.factory = SimpleFactory("testing", mocker.MagicMock(return_value=self.default_value))
        self.factory.register(MockType.Registered, mocker.MagicMock(return_value=self.registered_value))

    def test_factory_type(self):
        """测试 factory_type 默认值"""

        assert self.factory.factory_type == "simple"
        assert self.registered_value != self.default_value

    def test_make_registered(self):
        """测试构造已注册的类型"""

        assert self.factory.make(MockType.Registered) == self.registered_value

    def test_make_unregistered(self):
        """测试构造未注册的类型，返回默认值"""

        assert self.factory.make(MockType.NotRegister) == self.default_value

    def test_must_make_registered(self):
        """测试构造已注册的类型，不抛出异常"""

        assert self.factory.must_make(MockType.Registered) == self.registered_value

    def test_must_make_unregistered(self):
        """测试构造未注册的类型，抛出异常"""

        with pytest.raises(RuntimeError):
            self.factory.must_make(MockType.NotRegister)

    def test_call_with_none(self):
        """测试不传入参数时，返回默认值"""

        assert self.factory() == self.default_value

    def test_getitem(self):
        """通过下标创建"""

        callback = self.factory[MockType.Registered]

        assert callback() == self.registered_value
