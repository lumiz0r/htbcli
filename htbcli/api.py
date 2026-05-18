import requests
from requests.exceptions import RequestException, HTTPError

from .config import load_machines_cache, save_machines_cache

BASE_V4 = "https://labs.hackthebox.com/api/v4"
BASE_V5 = "https://labs.hackthebox.com/api/v5"
_WARMUP_URL = "https://labs.hackthebox.com/"


class HTBError(Exception):
    pass


class HTBAuthError(HTBError):
    pass


class HTBClient:
    def __init__(self, token: str):
        self._s = requests.Session()
        self._s.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Origin": "https://app.hackthebox.com",
                "Referer": "https://app.hackthebox.com/",
            }
        )
        self._warmed = False

    def _warmup(self) -> None:
        if not self._warmed:
            self._s.get(_WARMUP_URL, timeout=8)
            self._warmed = True

    # ── low-level ────────────────────────────────────────────────────────────

    def _get(self, base: str, path: str, **params):
        url = f"{base}{path}"
        try:
            r = self._s.get(url, params=params or None, timeout=15)
            if r.status_code == 401:
                raise HTBAuthError("Invalid or expired token. Run `htb auth` again.")
            r.raise_for_status()
            # Cloudflare blocking → warm up and retry once
            if "json" not in r.headers.get("content-type", ""):
                self._warmup()
                r = self._s.get(url, params=params or None, timeout=15)
                if r.status_code == 401:
                    raise HTBAuthError("Invalid or expired token. Run `htb auth` again.")
                r.raise_for_status()
            return r.json()
        except HTTPError as e:
            raise HTBError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except RequestException as e:
            raise HTBError(str(e)) from e

    def _post(self, path: str, data: dict):
        url = f"{BASE_V4}{path}"
        try:
            r = self._s.post(url, json=data, timeout=20)
            if r.status_code == 401:
                raise HTBAuthError("Invalid or expired token. Run `htb auth` again.")
            r.raise_for_status()
            return r.json()
        except HTTPError as e:
            raise HTBError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except RequestException as e:
            raise HTBError(str(e)) from e

    # ── machines ─────────────────────────────────────────────────────────────

    def get_machines(self, term: str = "", force_refresh: bool = False) -> list[dict]:
        """
        Returns all machines. Uses a local 6-hour cache to avoid re-fetching 530 machines
        on every command. Pass force_refresh=True to bust the cache.
        """
        if not force_refresh:
            cached = load_machines_cache()
            if cached is not None:
                if term:
                    tl = term.lower()
                    return [m for m in cached if tl in m.get("name", "").lower()]
                return cached

        # Full fetch: paginate through all pages
        all_machines: list[dict] = []
        page = 1
        while True:
            resp = self._get(BASE_V5, "/machines", page=page, per_page=100)
            data = resp.get("data", [])
            all_machines.extend(data)
            meta = resp.get("meta", {})
            if page >= meta.get("last_page", 1):
                break
            page += 1

        save_machines_cache(all_machines)

        if term:
            tl = term.lower()
            return [m for m in all_machines if tl in m.get("name", "").lower()]
        return all_machines

    def get_machine_profile(self, machine_id: int) -> dict:
        resp = self._get(BASE_V4, f"/machine/profile/{machine_id}")
        return resp.get("info", resp)

    def get_machine_matrix(self, machine_id: int) -> dict:
        resp = self._get(BASE_V4, f"/machine/graph/matrix/{machine_id}")
        return resp.get("info", {})

    # ── vm control ───────────────────────────────────────────────────────────

    def spawn(self, machine_id: int) -> dict:
        return self._post("/vm/spawn", {"machine_id": machine_id})

    def terminate(self, machine_id: int) -> dict:
        return self._post("/vm/terminate", {"machine_id": machine_id})

    def reset(self, machine_id: int) -> dict:
        return self._post("/vm/reset", {"machine_id": machine_id})

    def get_active_machine(self) -> dict | None:
        resp = self._get(BASE_V4, "/machine/active")
        return resp.get("info")

    # ── flags ────────────────────────────────────────────────────────────────

    def submit_flag(self, machine_id: int, flag: str, difficulty: int = 50) -> dict:
        return self._post("/machine/own", {"id": machine_id, "flag": flag, "difficulty": difficulty})

    # ── user ─────────────────────────────────────────────────────────────────

    def get_profile(self) -> dict:
        info = self._get(BASE_V4, "/user/info").get("info", {})
        user_id = info.get("id")
        if user_id:
            profile = self._get(BASE_V4, f"/user/profile/basic/{user_id}").get("profile", {})
            profile.setdefault("subscriptionType", info.get("subscriptionType"))
            return profile
        return info
