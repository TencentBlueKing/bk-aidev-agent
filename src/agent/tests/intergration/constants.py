from environs import Env

env = Env()

# 需要额外在集成测试中使用的环境变量定义如下

TEST_DEFAULT_MODEL = env.str("TEST_DEFAULT_MODEL", "hunyuan")
