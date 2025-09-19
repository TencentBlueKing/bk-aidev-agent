from aidev_agent.api.ssm_client import SSMClient

BASE_URL = "https://bkssm.sg.crosgame.com"  # 或 bkop 域名https://bkssm.bkop.woa.com
APP_CODE = "bk_aidev"
APP_SECRET = "O9LMgQ32mxJh8wzTKn6QfO4apSb1la0bGZtd"
BK_TOKEN = "O9LMgQ32mxJh8wzTKn6QfO4apSb1la0bGZtd"  # 用户态

client = SSMClient(BASE_URL, APP_CODE, APP_SECRET)

# 用户态
result = client.create_access_token("authorization_code", "bk_login", bk_token=BK_TOKEN)
print("生成 access_token 返回:", result)

# 应用态
# result = client.create_access_token("client_credentials", "client")
# print("client_credentials 生成 access_token 返回:", result)
