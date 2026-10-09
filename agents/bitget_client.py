"""Bitget REST client — no raise_for_status so we see real errors."""
import hmac, hashlib, base64, json, time, requests
from config import BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE

BASE = "https://api.bitget.com"


def _sign(secret, ts, method, path, body=""):
    msg = ts + method.upper() + path + body
    mac = hmac.new(secret.encode(), msg.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


class BitgetClient:
    def __init__(self):
        self.key = BITGET_API_KEY
        self.secret = BITGET_API_SECRET
        self.passphrase = BITGET_PASSPHRASE

    def _headers(self, method, path, body=""):
        ts = str(int(time.time() * 1000))
        return {
            "ACCESS-KEY": self.key,
            "ACCESS-SIGN": _sign(self.secret, ts, method, path, body),
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": "en-US",
            "paptrading": "1",
        }

    def public_get(self, path, params=None):
        r = requests.get(BASE + path, params=params, timeout=10)
        return r.json()

    def private_get(self, path, params=None):
        qs = "?" + "&".join(f"{k}={v}" for k, v in (params or {}).items()) if params else ""
        full = path + qs
        r = requests.get(BASE + full, headers=self._headers("GET", full), timeout=10)
        return r.json()

    def private_post(self, path, body_dict):
        body = json.dumps(body_dict)
        r = requests.post(BASE + path, headers=self._headers("POST", path, body),
                          data=body, timeout=10)
        try:
            return r.json()
        except Exception:
            return {"http_status": r.status_code, "body": r.text[:500]}
