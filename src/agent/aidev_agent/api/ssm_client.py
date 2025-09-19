from typing import Any, Dict, Optional

import requests


class SSMClient:
    def __init__(self, base_url: str, app_code: str, app_secret: str, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.app_code = app_code
        self.app_secret = app_secret
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Bk-App-Code": self.app_code,
            "X-Bk-App-Secret": self.app_secret,
            "Content-Type": "application/json",
        }

    def create_access_token(
        self,
        grant_type: str,
        id_provider: str,
        bk_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/auth/access-tokens"
        payload = {
            "grant_type": grant_type,
            "id_provider": id_provider,
        }
        if bk_token:
            payload["bk_token"] = bk_token
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/auth/access-tokens/refresh"
        payload = {"refresh_token": refresh_token}
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def verify_access_token(self, access_token: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/auth/access-tokens/verify"
        payload = {"access_token": access_token}
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
