"""Request and worker resource manager with identical authentication semantics."""

from typing import Any

from .agent_builder import LLMOverrideResourceManager


class PluginResourceManager(LLMOverrideResourceManager):
    """带用户态认证注入的资源管理器。

    传入 ``username``，基类 ``get_client()`` 自动通过 bkoauth 取 ``access_token`` 注入到 client header。
    view 层经 ``PluginViewSet.get_resource_manager()`` 按请求构造，并向下注入给
    ``SessionManager`` / ``AgentBuilder`` / ``AGUISessionWriter``，取代历史上的
    ``resource_manager()`` 全局单例。

    继承 ``LLMOverrideResourceManager`` 以携带 ``model`` 覆盖能力：view 层构造时 ``model`` 为空，
    由 ``AgentBuilder`` 在装配 agent 时按请求补上，使模型热更新与用户态认证共存于同一个 rm。
    """

    def __init__(self, username: str, model: str = "", *, app_code: str = "", app_secret: str = ""):
        super().__init__(username=username, model=model, app_code=app_code, app_secret=app_secret)
        self._cached_client = None

    def get_client(self, **kwargs: Any):
        """按实例缓存 ``client``。

        基类每次 ``get_client()`` 都会 ``resolve_access_token``，即一次 bkoauth ``AccessToken``
        表查询（token 临期还会同步发请求续期）。本类是请求级对象，同一实例上的 client 可安全复用，
        避免 ``SessionManager`` 等多次取 client 时反复查库。
        带 ``kwargs`` 的调用参数各异，不参与缓存。
        """
        if kwargs:
            return super().get_client(**kwargs)
        if self._cached_client is None:
            self._cached_client = super().get_client()
        return self._cached_client


# Applications with request-scoped resource managers register a codec during
# startup in both Web and worker processes. Payloads carry configuration keys,
# never Python classes, clients, or application/user credentials.
_task_codecs = {}
_task_loaders = {}


def register_task_resource_manager(name, manager_type, encode, decode):
    if name == "application" or name in _task_loaders or manager_type in _task_codecs:
        raise ValueError("Resource manager task codec is already registered")
    _task_codecs[manager_type] = (name, encode)
    _task_loaders[name] = decode


def encode_task_resource_manager(manager):
    if type(manager) is not PluginResourceManager:
        codec = _task_codecs.get(type(manager))
        if codec is None:
            raise TypeError("Register a task codec for the custom Web resource manager")
        name, encode = codec
        return {"kind": name, "options": encode(manager)}
    default = PluginResourceManager(username=manager.username, model=manager.model)
    if (manager.app_code, manager.app_secret, manager.access_token) != (
        default.app_code,
        default.app_secret,
        default.access_token,
    ):
        raise ValueError("Web Celery execution requires worker-local application credentials")
    return {"kind": "application", "options": {"username": manager.username, "model": manager.model}}


def decode_task_resource_manager(context):
    if context["kind"] == "application":
        return PluginResourceManager(**context["options"])
    return _task_loaders[context["kind"]](context["options"])
