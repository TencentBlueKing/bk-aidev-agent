# -*- coding: utf-8 -*-


class AIDevException(Exception):
    ERROR_CODE = "500"
    MESSAGE = "APP异常"

    def __init__(self, *args, message: str | None = None):
        self.message = message or self.MESSAGE

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message})"


class AgentException(AIDevException):
    MESSAGE = "Agent异常"
