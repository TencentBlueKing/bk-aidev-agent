# 这个模块用于声明测试相关的 Fixture 类型，方便测试代码编写时的类型提示引用

from typing import Any, Callable, Dict, TypeVar
from unittest import mock

import pytest
from faker import Faker
from faker.providers.address import Provider as AddressProvider
from faker.providers.color import Provider as ColorProvider
from faker.providers.date_time import Provider as DateTimeProvider
from faker.providers.file import Provider as FileProvider
from faker.providers.internet import Provider as InternetProvider
from faker.providers.lorem import Provider as LoremProvider
from faker.providers.person import Provider as PersonProvider
from faker.providers.python import Provider as PythonProvider
from pytest_mock import MockFixture
from typing_extensions import Protocol, TypeAlias


class TypedFaker(  # noqa
    Faker,
    InternetProvider,
    ColorProvider,
    PersonProvider,
    AddressProvider,
    DateTimeProvider,
    FileProvider,
    PythonProvider,
    LoremProvider,
):
    """Faker 类型注解，方便使用"""


class PatchedPytestCallSpec(Protocol):
    params: Dict[str, Any]
    indices: Dict[str, int]


class PytestRequestNode(pytest.Item):
    callspec: PatchedPytestCallSpec


class PatchedFixtureRequest(pytest.FixtureRequest):
    """FixtureRequest 类型注解，方便使用"""

    node: PytestRequestNode


class BenchmarkProtocol(Protocol):
    T = TypeVar("T")

    def __call__(self, function_to_benchmark: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """执行基准测试，会使用相同的参数调用被测试函数多次"""
        ...


class BuiltInFixtureType:
    """内置 Fixture 类型"""

    # 这里声明第三方模块提供的 Fixture
    faker: TypeAlias = TypedFaker
    mocker: TypeAlias = MockFixture
    request: TypeAlias = PatchedFixtureRequest
    benchmark: TypeAlias = BenchmarkProtocol
    MagicMock: TypeAlias = mock.MagicMock


class CoreFixtureType:
    """核心 Fixture 类型"""

    # 这里只能声明 tests/conftest.py 中定义的 Fixture


class FixtureType(BuiltInFixtureType):
    """测试 Fixture 类型，实际生效的 fixture 以 pytest 为准，此处仅提供辅助的类型注释"""
