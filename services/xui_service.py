"""
xui_service.py — سازگار با همه نسخه‌های 3x-ui
- نسخه قدیمی: POST /login بدون CSRF
- نسخه جدید (v3+): CSRF token + فرمت جدید addClient
"""
import uuid, json, base64, secrets, string, urllib.parse
import aiohttp
from datetime import datetime, timedelta
from database.db import get_server, get_best_server, save_xui_account


def _rand(n=16):
    return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def sanitize_config_name(name: str) -> str:
    """نام کانفیگ انتخابیِ مشتری را به یک ایمیل/شناسهٔ امن برای X-UI تبدیل می‌کند."""
    if not name:
        return ""
    keep = []
    for ch in str(name).strip():
        if ch.isalnum() or ch in "_-.":
            keep.append(ch)
        elif ch.isspace():
            keep.append("_")
    out = "".join(keep).strip("._-")
    return out[:32]


class XUIClient:
    def __init__(self, server: dict):
        self.server = server
        self.base_url = server["url"].rstrip("/")
        self.username = server["username"]
        self.password = server["password"]
        # دامنهٔ دستیِ سرور (اگر ادمین در بات ست کرده باشد) — اولویت با این
        try:
            self.server_domain = (server.get("domain") or "").strip()
        except Exception:
            self.server_domain = ""
        self._session = None
        self._csrf = None
        # کش Hosts پنل (بخش Hosts در 3x-ui v3.4+): {inboundId: host_dict}
        self._hosts_by_inbound = {}
        self._hosts_loaded = False

    async def _sess(self):
        if not self._session or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=20),
                cookie_jar=jar,
                headers={
                    "User-Agent": "Mozilla/5.0 Chrome/124.0 Safari/537.36",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self):
        s = await self._sess()
        body = urllib.parse.urlencode({"username": self.username, "password": self.password})
        hdr = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}

        # روش 1: قدیمی
        try:
            r = await s.post(f"{self.base_url}/login", data=body, headers=hdr)
            if r.status == 200:
                d = json.loads(await r.text())
                if d.get("success"):
                    return True, "✅ لاگین موفق"
        except aiohttp.ClientConnectorError:
            return False, "❌ اتصال ناموفق"
        except Exception:
            pass

        # روش 2: جدید با CSRF
        try:
            await s.get(f"{self.base_url}/")
            cr = await s.get(f"{self.base_url}/csrf-token")
            if cr.status == 200:
                cd = await cr.json()
                if cd.get("success") and cd.get("obj"):
                    self._csrf = cd["obj"]
                    r2 = await s.post(f"{self.base_url}/login", data=body,
                                      headers={**hdr, "X-CSRF-Token": self._csrf})
                    if r2.status == 200:
                        d2 = json.loads(await r2.text())
                        if d2.get("success"):
                            return True, "✅ لاگین موفق"
                        return False, f"❌ {d2.get('msg', 'یوزر/پسورد اشتباه')}"
        except Exception as e:
            return False, f"❌ {e}"

        return False, "❌ لاگین ناموفق"

    async def _refresh_csrf(self):
        s = await self._sess()
        try:
            cr = await s.get(f"{self.base_url}/csrf-token")
            if cr.status == 200:
                d = await cr.json()
                if d.get("success"):
                    self._csrf = d["obj"]
        except Exception:
            pass

    def _h_json(self):
        h = {"Content-Type": "application/json"}
        if self._csrf:
            h["X-CSRF-Token"] = self._csrf
        return h

    def _h_form(self):
        h = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        if self._csrf:
            h["X-CSRF-Token"] = self._csrf
        return h

    async def get_inbounds(self):
        s = await self._sess()
        # یک‌بار Hosts پنل را کش کن تا build_vless_link خودکار دامنهٔ درست را بگذارد
        if not self._hosts_loaded:
            try:
                await self.load_hosts()
            except Exception:
                self._hosts_by_inbound = {}
            self._hosts_loaded = True
        for ep in ["/panel/api/inbounds/list", "/xui/inbound/list", "/panel/inbound/list"]:
            try:
                r = await s.get(f"{self.base_url}{ep}")
                if r.status == 200:
                    d = await r.json()
                    if d.get("success"):
                        return d.get("obj", [])
            except Exception:
                continue
        return []

    async def load_hosts(self):
        """
        بخش Hosts پنل (3x-ui v3.4+) دامنه/endpoint هر اینباند را نگه می‌دارد.
        این را می‌خوانیم تا لینک کانفیگ خودکار با دامنهٔ درستِ پنل ساخته شود
        (ریشه‌ای؛ نیازی به دامنهٔ دستی نیست). {inboundId: host} پر می‌شود.
        """
        try:
            s = await self._sess()
            await self._refresh_csrf()
            r = await s.get(f"{self.base_url}/panel/api/hosts/list", headers=self._h_json())
            if r.status == 200:
                d = await r.json()
                if d.get("success"):
                    mapping = {}
                    for h in (d.get("obj") or []):
                        if h.get("isDisabled"):
                            continue
                        ib_id = h.get("inboundId")
                        if ib_id is not None and h.get("address"):
                            # اولین host فعال برای هر اینباند
                            if ib_id not in mapping:
                                mapping[ib_id] = h
                    self._hosts_by_inbound = mapping
        except Exception:
            pass
        return self._hosts_by_inbound

    async def add_client(self, inbound_ids, email: str,
                         traffic_gb: int, duration_days: int,
                         expiry_ms: int = None, traffic_bytes_override: int = None):
        """
        افزودن کلاینت به یک یا چند اینباند (پروتکل‌محور).
        inbound_ids می‌تواند int یا list باشد.

        expiry_ms: اگر داده شود، مستقیماً به‌عنوان expiryTime استفاده می‌شود
                   (برای اکانت تست با مدت ساعتی دقیق).
        traffic_bytes_override: اگر داده شود، مستقیماً به‌عنوان totalGB بایتی
                   استفاده می‌شود (برای حجم مگابایتیِ اکانت تست).
        """
        if isinstance(inbound_ids, (list, tuple)):
            ids = [int(i) for i in inbound_ids]
        else:
            ids = [int(inbound_ids)]
        if not ids:
            return None

        s = await self._sess()
        await self._refresh_csrf()

        cid = str(uuid.uuid4())
        sub_id = _rand(16)
        client_pw = _rand(20)  # برای shadowsocks / trojan password
        if expiry_ms is not None:
            expire_ms = int(expiry_ms)
        else:
            expire_ms = int((datetime.now() + timedelta(days=duration_days)).timestamp() * 1000) if duration_days > 0 else 0
        if traffic_bytes_override is not None:
            traffic_bytes = int(traffic_bytes_override)
        else:
            traffic_bytes = int(traffic_gb) * 1024 ** 3 if traffic_gb else 0

        client = {
            "id": cid, "email": email, "enable": True,
            "expiryTime": expire_ms, "totalGB": traffic_bytes,
            "limitIp": 0, "tgId": 0, "subId": sub_id,
            "flow": "", "comment": "", "reset": 0,
            "password": client_pw,  # برای اینباندهای shadowsocks/trojan
        }

        def _ok(result):
            return {"client_id": cid, "email": email, "sub_id": sub_id, "password": client_pw}

        # ── روش 1: فرمت v3+ — همهٔ اینباندها در یک درخواست ──
        try:
            payload = {"inboundIds": ids, "client": client}
            r = await s.post(f"{self.base_url}/panel/api/clients/add",
                             json=payload, headers=self._h_json())
            if r.status == 200:
                d = await r.json()
                if d.get("success"):
                    return _ok(d)
        except Exception:
            pass

        # ── روش 2: فرمت v2 کلاسیک — هر اینباند جداگانه ──
        any_ok = False
        for inbound_id in ids:
            classic = {"id": inbound_id, "settings": json.dumps({"clients": [client]})}
            for ep in ["/panel/api/inbounds/addClient",
                       "/xui/inbound/addClient",
                       "/panel/inbound/addClient"]:
                try:
                    r = await s.post(f"{self.base_url}{ep}",
                                     data=urllib.parse.urlencode(classic),
                                     headers=self._h_form())
                    if r.status == 200:
                        d = await r.json()
                        if d.get("success"):
                            any_ok = True
                            break
                except Exception:
                    continue
        return _ok(None) if any_ok else None

    async def _find_client_raw(self, email: str):
        """
        کلاینت را در اینباندها پیدا می‌کند و (inbound_id, client_dict, stats) را برمی‌گرداند.
        client_dict همان تنظیمات ذخیره‌شدهٔ کلاینت (id/subId/flow/...) است.
        """
        target = (email or "").strip()
        inbounds = await self.get_inbounds()
        for ib in inbounds:
            try:
                settings = self._parse(ib.get("settings", {}))
                for cl in (settings.get("clients") or []):
                    if str(cl.get("email", "")).strip() == target:
                        # آمار مصرف/انقضای فعلی از clientStats
                        st = None
                        for s in (ib.get("clientStats") or []):
                            if str(s.get("email", "")).strip() == target:
                                st = s
                                break
                        return ib.get("id"), cl, st
            except Exception:
                continue
        return None, None, None

    async def _apply_client_update(self, ib_id, email, mutate):
        """
        کلاینت را با به‌روزرسانیِ «کلِ اینباند» تغییر می‌دهد (سازگار با نسخهٔ پنلی
        که updateClient روی آن 404 می‌دهد).

        mutate: تابعی که dictِ کلاینت را می‌گیرد و در جا تغییرش می‌دهد.
        روش: کل اینباند را می‌گیریم، کلاینت موردنظر را در settings تغییر می‌دهیم،
        و کل اینباند را با JSON به /panel/api/inbounds/update/{id} می‌فرستیم.
        """
        s = await self._sess()
        await self._refresh_csrf()

        # کل اینباند را تازه بگیر
        inbounds = await self.get_inbounds()
        ib = None
        for x in inbounds:
            if int(x.get("id", 0)) == int(ib_id):
                ib = x
                break
        if not ib:
            return False

        settings = self._parse(ib.get("settings", {}))
        found = False
        for cl in settings.get("clients", []):
            if str(cl.get("email", "")).strip() == str(email).strip():
                mutate(cl)
                found = True
                break
        if not found:
            return False

        payload = dict(ib)
        payload["settings"] = json.dumps(settings)
        # فیلدهای تودرتو باید رشتهٔ JSON باشند
        for k in ["streamSettings", "sniffing", "allocate"]:
            if k in payload and not isinstance(payload[k], str):
                payload[k] = json.dumps(payload[k])
        # فیلدهای محاسباتی که نباید فرستاده شوند
        payload.pop("clientStats", None)

        try:
            r = await s.post(f"{self.base_url}/panel/api/inbounds/update/{ib_id}",
                             json=payload, headers=self._h_json())
            if r.status == 200:
                d = await r.json()
                return bool(d.get("success"))
        except Exception:
            pass
        return False

    async def delete_client_by_email(self, email: str):
        """کلاینت را با حذف از settingsِ کل اینباند حذف می‌کند (سازگار با این پنل)."""
        ib_id, client, st = await self._find_client_raw(email)
        if not client or ib_id is None:
            return False
        s = await self._sess()
        await self._refresh_csrf()
        inbounds = await self.get_inbounds()
        ib = None
        for x in inbounds:
            if int(x.get("id", 0)) == int(ib_id):
                ib = x
                break
        if not ib:
            return False
        settings = self._parse(ib.get("settings", {}))
        before = len(settings.get("clients", []))
        settings["clients"] = [c for c in settings.get("clients", [])
                               if str(c.get("email", "")).strip() != str(email).strip()]
        if len(settings["clients"]) == before:
            return False
        payload = dict(ib)
        payload["settings"] = json.dumps(settings)
        for k in ["streamSettings", "sniffing", "allocate"]:
            if k in payload and not isinstance(payload[k], str):
                payload[k] = json.dumps(payload[k])
        payload.pop("clientStats", None)
        try:
            r = await s.post(f"{self.base_url}/panel/api/inbounds/update/{ib_id}",
                             json=payload, headers=self._h_json())
            if r.status == 200:
                return bool((await r.json()).get("success"))
        except Exception:
            pass
        return False

    async def reset_client_traffic(self, ib_id: int, email: str) -> bool:
        """
        ریست ترافیک مصرف‌شدهٔ کلاینت (up/down → صفر).

        این پنل (v3.4.2) endpoint استانداردِ resetClientTraffic را ندارد و
        clientStats از طریق آپدیت اینباند فقط-خواندنی است. بنابراین از روش
        «حذف و بازسازیِ کلاینت با حفظ کامل مشخصات» استفاده می‌کنیم:
        uuid/email/subId/password/totalGB/expiryTime همگی حفظ می‌شوند، پس
        لینک کانفیگِ کاربر هیچ تغییری نمی‌کند؛ فقط شمارندهٔ مصرف صفر می‌شود.

        اگر پنل روزی endpoint استاندارد داشته باشد، ابتدا آن امتحان می‌شود.
        """
        s = await self._sess()
        await self._refresh_csrf()

        # ۱) تلاش با endpoint استاندارد (اگر پنل پشتیبانی کند)
        for ep in [
            f"/panel/api/inbounds/{int(ib_id)}/resetClientTraffic/{email}",
            f"/panel/inbound/{int(ib_id)}/resetClientTraffic/{email}",
        ]:
            try:
                r = await s.post(f"{self.base_url}{ep}", headers=self._h_json())
                if r.status == 200 and bool((await r.json()).get("success")):
                    return True
            except Exception:
                pass

        # ۲) روش سازگار: حذف و بازسازی با حفظ کامل مشخصات
        try:
            import copy
            inbounds = await self.get_inbounds()
            ib = next((x for x in inbounds if int(x.get("id", 0)) == int(ib_id)), None)
            if not ib:
                return False
            settings = self._parse(ib.get("settings", {}))
            saved = next((cl for cl in settings.get("clients", [])
                          if str(cl.get("email", "")).strip() == str(email).strip()), None)
            if not saved:
                return False
            saved = copy.deepcopy(saved)

            # مرحلهٔ حذف
            settings["clients"] = [cl for cl in settings.get("clients", [])
                                   if str(cl.get("email", "")).strip() != str(email).strip()]
            payload = dict(ib)
            payload["settings"] = json.dumps(settings)
            for k in ["streamSettings", "sniffing", "allocate"]:
                if k in payload and not isinstance(payload[k], str):
                    payload[k] = json.dumps(payload[k])
            payload.pop("clientStats", None)
            r1 = await s.post(f"{self.base_url}/panel/api/inbounds/update/{int(ib_id)}",
                              json=payload, headers=self._h_json())
            if r1.status != 200 or not bool((await r1.json()).get("success")):
                return False

            # مرحلهٔ بازسازی با همان مشخصات
            await self._refresh_csrf()
            inbounds2 = await self.get_inbounds()
            ib2 = next((x for x in inbounds2 if int(x.get("id", 0)) == int(ib_id)), None)
            if not ib2:
                return False
            settings2 = self._parse(ib2.get("settings", {}))
            settings2.setdefault("clients", []).append(saved)
            payload2 = dict(ib2)
            payload2["settings"] = json.dumps(settings2)
            for k in ["streamSettings", "sniffing", "allocate"]:
                if k in payload2 and not isinstance(payload2[k], str):
                    payload2[k] = json.dumps(payload2[k])
            payload2.pop("clientStats", None)
            r2 = await s.post(f"{self.base_url}/panel/api/inbounds/update/{int(ib_id)}",
                              json=payload2, headers=self._h_json())
            return r2.status == 200 and bool((await r2.json()).get("success"))
        except Exception:
            return False

    async def renew_client(self, email: str, add_traffic_gb: int, add_days: int):
        """
        تمدید کلاینت موجود — منطق «ریست و جایگزینی» (طبق خواستهٔ کارفرما):

        - ترافیک مصرف‌شده همیشه ریست می‌شود (مصرف → صفر).
        - حجم کل روی مقدار پلنِ انتخابی «تنظیم» می‌شود (نه اضافه).
          اگر پلن نامحدود باشد (۰)، نامحدود می‌ماند.
        - مدت از «حالا» به‌اندازهٔ مدت پلن تنظیم می‌شود (نه اضافه به تاریخ قبلی).
          یعنی اگر ۱۵ روز مانده بود و پلن ۳۰ روزه بود، دوباره ۳۰ روز کامل از حالا.
        - اکانت همیشه فعال می‌شود (اگر غیرفعال بود، فعال می‌شود).

        مثال‌ها:
        - همان پلن ۱ ماهه ۱۰ گیگ (۱۵ روز مانده): مصرف صفر، حجم ۱۰ گیگ، ۳۰ روز از حالا.
        - پلن جدید ۳ ماهه ۲۰ گیگ: مصرف صفر، حجم ۲۰ گیگ، ۹۰ روز از حالا.
        """
        ib_id, client, st = await self._find_client_raw(email)
        if not client or ib_id is None:
            return None

        now_ms = int(datetime.now().timestamp() * 1000)

        cur_exp = int(client.get("expiryTime", 0) or 0)
        was_expired = bool(cur_exp) and cur_exp <= now_ms

        # حجم جدید = مقدار پلن (تنظیم، نه اضافه)؛ ۰ یا خالی → نامحدود
        new_total = int(add_traffic_gb) * 1024 ** 3 if add_traffic_gb else 0

        # مدت جدید = از حالا + مدت پلن (جایگزینی کامل، نه اضافه به تاریخ قبلی)
        add_ms = int(add_days) * 24 * 3600 * 1000 if add_days else 0
        new_exp = (now_ms + add_ms) if add_ms else 0  # ۰ = بی‌انقضا

        def _mut(cl):
            cl["totalGB"] = new_total
            cl["expiryTime"] = new_exp
            cl["enable"] = True
            # فیلدهای شمارندهٔ داخلی برخی نسخه‌ها هم صفر شوند (بی‌ضرر اگر نباشند)
            cl["up"] = 0
            cl["down"] = 0

        ok = await self._apply_client_update(ib_id, email, _mut)
        if not ok:
            return None

        # ریست واقعی ترافیک مصرف‌شده در پنل (up/down در clientStats)
        traffic_reset = await self.reset_client_traffic(ib_id, email)

        return {
            "email": email,
            "was_expired": was_expired,
            "traffic_reset": traffic_reset,
            "new_total_gb": (round(new_total / 1024 ** 3, 2) if new_total else 0),
            "new_expiry": (datetime.fromtimestamp(new_exp / 1000).strftime("%Y-%m-%d")
                           if new_exp else "نامحدود"),
            "new_expiry_full": (datetime.fromtimestamp(new_exp / 1000).strftime("%Y-%m-%d %H:%M:%S")
                                if new_exp else ""),
        }

    async def get_client_stats(self, email: str):
        target = (email or "").strip()
        # روش اصلی: clientStats داخل اینباندها (سازگار با نسخهٔ فعلی پنل که getClientTraffics ندارد)
        try:
            inbounds = await self.get_inbounds()
            for ib in inbounds:
                for st in (ib.get("clientStats") or []):
                    if str(st.get("email", "")).strip() == target:
                        return {
                            "up": st.get("up", 0) or 0,
                            "down": st.get("down", 0) or 0,
                            "total": st.get("total", 0) or 0,
                            "enable": st.get("enable", True),
                        }
        except Exception:
            pass
        # fallback: endpoint قدیمی (اگر پنل پشتیبانی کند)
        s = await self._sess()
        for ep in [f"/panel/api/inbounds/getClientTraffics/{email}",
                   f"/xui/inbound/getClientTraffics/{email}"]:
            try:
                r = await s.get(f"{self.base_url}{ep}")
                if r.status == 200:
                    d = await r.json()
                    if d.get("success") and d.get("obj"):
                        return d["obj"]
            except Exception:
                continue
        return None

    @staticmethod
    def _parse(field):
        if isinstance(field, dict):
            return field
        try:
            return json.loads(field)
        except Exception:
            return {}

    def build_vless_link(self, inbound: dict, client_id: str, email: str, password: str = ""):
        try:
            stream = self._parse(inbound.get("streamSettings", {}))
            protocol = (inbound.get("protocol", "vless") or "vless").lower()
            raw = self.base_url.replace("https://", "").replace("http://", "")
            host = raw.split(":")[0].split("/")[0]
            port = inbound.get("port", 443)
            network = stream.get("network", "tcp")
            security = stream.get("security", "none")

            # اگر External Proxy (دامنه) روی اینباند ست شده باشد، به‌جای IP پنل از آن استفاده کن
            ext = stream.get("externalProxy") or []
            if isinstance(ext, list) and ext:
                e0 = ext[0] or {}
                if e0.get("dest"):
                    host = str(e0["dest"]).strip()
                if e0.get("port"):
                    try:
                        port = int(e0["port"])
                    except Exception:
                        pass
                if e0.get("forceTls") in ("tls", "reality") and security == "none":
                    security = e0["forceTls"]

            # ریشه‌ای: دامنه از بخش Hosts پنل (خودکار؛ هر وقت مشتری عوض کند اعمال می‌شود)
            host_entry = (self._hosts_by_inbound or {}).get(inbound.get("id"))
            if host_entry and host_entry.get("address"):
                host = str(host_entry["address"]).strip()
                if host_entry.get("port"):
                    try:
                        port = int(host_entry["port"])
                    except Exception:
                        pass
                _hsec = host_entry.get("security")
                if _hsec and _hsec not in ("same", "none"):
                    security = _hsec
                if host_entry.get("sni"):
                    stream.setdefault("_hostSni", host_entry["sni"])

            # بالاترین اولویت (اختیاری): دامنهٔ دستیِ ست‌شده در بات
            if self.server_domain:
                host = self.server_domain

            # نام کانفیگ = «remark اینباند - اسم انتخابیِ مشتری»
            remark = str(inbound.get("remark") or "").strip()
            if not remark and host_entry:
                remark = str(host_entry.get("remark") or "").strip()
            tag = (remark + "-" + email) if remark else email

            if protocol == "vless":
                params = f"type={network}&security={security}"
                if security == "reality":
                    rs = stream.get("realitySettings", {})
                    si = rs.get("settings", {})
                    params += f"&pbk={si.get('publicKey', '')}&fp={si.get('fingerprint', 'chrome')}"
                    sids = rs.get("shortIds", [])
                    if sids:
                        params += f"&sid={sids[0]}"
                    dest = rs.get("dest", "")
                    if dest:
                        params += f"&sni={dest.split(':')[0]}"
                elif security == "tls":
                    tls = stream.get("tlsSettings", {})
                    if tls.get("serverName"):
                        params += f"&sni={tls['serverName']}"
                if network == "ws":
                    ws = stream.get("wsSettings", {})
                    params += f"&path={ws.get('path', '/')}"
                elif network == "grpc":
                    params += f"&serviceName={stream.get('grpcSettings', {}).get('serviceName', '')}"
                return f"vless://{client_id}@{host}:{port}?{params}#{tag}"

            elif protocol == "vmess":
                cfg = {"v": "2", "ps": tag, "add": host, "port": str(port),
                       "id": client_id, "aid": "0", "scy": "auto", "net": network,
                       "type": "none", "host": "", "tls": security,
                       "path": stream.get("wsSettings", {}).get("path", "/")}
                return "vmess://" + base64.b64encode(json.dumps(cfg).encode()).decode()

            elif protocol == "trojan":
                return f"trojan://{client_id}@{host}:{port}?type={network}&security={security}#{tag}"

            elif protocol in ("shadowsocks", "ss"):
                ss = self._parse(inbound.get("settings", {}))
                method = ss.get("method", "") or "aes-256-gcm"
                server_pw = ss.get("password", "")
                client_pw = password or server_pw
                # SS-2022 نیازمند ترکیب رمز سرور و کلاینت است
                if str(method).startswith("2022") and server_pw:
                    userinfo = f"{method}:{server_pw}:{client_pw}"
                else:
                    userinfo = f"{method}:{client_pw}"
                # base64 بدون padding (مطابق فرمت 3x-ui)
                b = base64.b64encode(userinfo.encode()).decode().rstrip("=")
                return f"ss://{b}@{host}:{port}?type={network}&security={security}#{tag}"
        except Exception:
            pass
        return None

    def build_links_for_inbounds(self, inbounds: list, client_id: str, email: str, password: str = "") -> list:
        """برای هر اینباند، لینک متناسب با پروتکل همان اینباند را می‌سازد."""
        out = []
        for ib in inbounds:
            try:
                link = self.build_vless_link(ib, client_id, email, password)
                if link:
                    out.append({"protocol": (ib.get("protocol", "") or "").lower(), "link": link})
            except Exception:
                continue
        return out

    async def find_client_by_email(self, query: str):
        """
        جستجوی کلاینت در همهٔ اینباندها بر اساس هر شناسه‌ای:
        email، id (UUID)، subId یا password — بدون حساسیت به بزرگی/کوچکی حروف.
        """
        q = (query or "").strip().lower()
        if not q:
            return None
        inbounds = await self.get_inbounds()
        for ib in inbounds:
            settings = self._parse(ib.get("settings", {}))
            for cl in settings.get("clients", []) or []:
                for field in ("email", "id", "subId", "password"):
                    v = str(cl.get(field, "")).strip().lower()
                    if v and v == q:
                        return {"inbound": ib, "client": cl}
        return None


async def test_server_connection(server: dict):
    c = XUIClient(server)
    try:
        ok, msg = await c.login()
        if not ok:
            return False, msg
        inbounds = await c.get_inbounds()
        return True, f"✅ اتصال موفق — {len(inbounds)} اینباند"
    except Exception as e:
        return False, f"❌ {e}"
    finally:
        await c.close()


async def get_inbounds_for_server(server: dict):
    c = XUIClient(server)
    try:
        ok, _ = await c.login()
        return await c.get_inbounds() if ok else []
    finally:
        await c.close()


async def provision_account(order_id: int, telegram_id: int,
                             plan, server_id=None, custom_name: str = "", name_suffix: str = ""):
    # سرور مقصد: اگر server_id داده شده ولی سرور وجود نداشت/غیرفعال بود،
    # به‌جای شکست، به بهترین سرور فعال fallback می‌کنیم (مثلاً وقتی سرور قدیمی حذف شده).
    server = get_server(server_id) if server_id else None
    if not server or not server.get("is_active", 1):
        server = get_best_server()
    if not server:
        return None
    c = XUIClient(server)
    try:
        ok, _ = await c.login()
        if not ok:
            # اگر سرور پین‌شده لاگین نشد، یک بار با بهترین سرور دیگر تلاش کن
            alt = get_best_server()
            if alt and alt.get("id") != server.get("id"):
                await c.close()
                server = alt
                c = XUIClient(server)
                ok, _ = await c.login()
            if not ok:
                return None
        inbounds = await c.get_inbounds()
        if not inbounds:
            return None
        active_ibs = [ib for ib in inbounds if ib.get("enable", True)] or inbounds
        # فقط از همان اینباندی که در «افزودن پلن» انتخاب شده بساز.
        # اگر اینباندی انتخاب نشده (inbound_id=0)، فقط اولین اینباند فعال استفاده می‌شود (یک کانفیگ).
        plan_ib = int(plan.get("inbound_id") or 0) if plan else 0
        if plan_ib:
            chosen = [ib for ib in inbounds if int(ib.get("id", 0)) == plan_ib]
            enabled = chosen or active_ibs[:1]
        else:
            enabled = active_ibs[:1]
        primary = enabled[0]
        ib_ids = [ib["id"] for ib in enabled]
        traffic_gb = int(plan.get("traffic_gb", 0)) if plan else 0
        duration_days = int(plan.get("duration_days", 30)) if plan else 30
        # نام دلخواه مشتری (اگر موقع خرید انتخاب کرده باشد) به‌عنوان remark/email کانفیگ
        email = f"u{telegram_id}_{order_id}"
        if custom_name and str(custom_name).strip():
            # نام صریحِ همین اکانت (سفارش چند-اکانتی: هر اکانت نام خودش را دارد)
            email = str(custom_name).strip()
        else:
            try:
                from database.db import get_connection
                _conn = get_connection()
                _cur = _conn.cursor()
                _cur.execute("SELECT config_name FROM orders WHERE id = ?", (order_id,))
                _row = _cur.fetchone()
                _conn.close()
                _cn = (str(_row["config_name"]).strip() if _row and _row["config_name"] else "")
                if _cn:
                    # config_name می‌تواند فهرست نام‌ها (جدا با کاما) باشد؛ اولی را بردار
                    email = _cn.split(",")[0].strip() or email
            except Exception:
                pass
        # برای سفارش چند-اکانتی، پسوند یکتا به نام هر کانفیگ اضافه می‌شود
        if name_suffix:
            email = email + name_suffix
        result = await c.add_client(ib_ids, email, traffic_gb, duration_days)
        if not result:
            return None
        password = result.get("password", "")
        # لینک برای هر اینباند فعال (هر پروتکلی که پنل دارد: vless/vmess/trojan/ss/...)
        all_links = c.build_links_for_inbounds(enabled, result["client_id"], email, password)
        config_link = all_links[0]["link"] if all_links else c.build_vless_link(primary, result["client_id"], email, password)
        expires_at = (datetime.now() + timedelta(days=duration_days)).strftime("%Y-%m-%d") if duration_days > 0 else "نامحدود"
        # بدون save_xui_account — caller انجام میده تا database locked نشه
        return {
            "config_link": config_link,
            "config_links": all_links,
            "config_type": (primary.get("protocol", "vless") or "vless"),
            "email": email,
            "client_id": result["client_id"],
            "password": password,
            "sub_id": result.get("sub_id", ""),
            "server_id": server["id"],
            "inbound_id": primary["id"],
            "server_label": server["label"],
            "expires_at": expires_at,
            "traffic_gb": traffic_gb,
        }
    except Exception:
        return None
    finally:
        await c.close()


async def get_account_stats(email: str, server_id: int):
    server = get_server(server_id)
    if not server:
        return None
    c = XUIClient(server)
    try:
        ok, _ = await c.login()
        if not ok:
            return None
        return await c.get_client_stats(email)
    finally:
        await c.close()


async def delete_account(email: str, server_id: int):
    """حذف اکانت از پنل (روی سرور مشخص)."""
    server = get_server(server_id)
    if not server:
        return False
    c = XUIClient(server)
    try:
        ok, _ = await c.login()
        if not ok:
            return False
        return await c.delete_client_by_email(email)
    finally:
        await c.close()


async def renew_account(email: str, server_id: int, plan_traffic_gb: int, plan_days: int):
    """
    تمدید اکانت موجود روی همان سرور — منطق «ریست و جایگزینی»:
    ترافیک ریست می‌شود، حجم روی مقدار پلن تنظیم می‌شود، و مدت از حالا شروع می‌شود.
    اگر اکانت غیرفعال بود، فعال می‌شود.
    خروجی: dict با new_total_gb / new_expiry / traffic_reset، یا None اگر ناموفق بود.
    """
    server = get_server(server_id)
    if not server or not server.get("is_active", 1):
        return None
    c = XUIClient(server)
    try:
        ok, _ = await c.login()
        if not ok:
            return None
        return await c.renew_client(email, plan_traffic_gb, plan_days)
    finally:
        await c.close()


async def provision_test_account(telegram_id: int, server_id: int, inbound_id: int,
                                  traffic_mb: int, duration_hours: int):
    """
    ساخت اکانت تست روی سرور/اینباند مشخص با حجم (مگابایت) و زمان (ساعت) دلخواه ادمین.
    - حجم بر حسب مگابایت است (اکانت تست کوچک است).
    - زمان دقیقاً بر حسب ساعت تنظیم می‌شود (مستقیماً expiryTime).
    - نام کاملاً رندوم با پیشوند test_.
    خروجی: dict شبیه provision_account، یا None.
    """
    server = get_server(server_id)
    if not server or not server.get("is_active", 1):
        return None
    c = XUIClient(server)
    try:
        ok, _ = await c.login()
        if not ok:
            return None
        inbounds = await c.get_inbounds()
        if not inbounds:
            return None
        chosen = [ib for ib in inbounds if int(ib.get("id", 0)) == int(inbound_id)]
        if not chosen:
            active = [ib for ib in inbounds if ib.get("enable", True)] or inbounds
            chosen = active[:1]
        primary = chosen[0]
        ib_ids = [ib["id"] for ib in chosen]

        # ایمیل یکتا با نام کاملاً رندوم (پیشوند test_ برای شناسایی ادمین)
        import secrets
        email = "test_" + secrets.token_hex(5)

        # زمان دقیق بر حسب ساعت + حجم بر حسب مگابایت — مستقیم به add_client
        exp_ms = int((datetime.now() + timedelta(hours=int(duration_hours))).timestamp() * 1000) if duration_hours else 0
        traffic_bytes = int(traffic_mb) * 1024 ** 2 if traffic_mb else 0

        result = await c.add_client(
            ib_ids, email, 0, 0,
            expiry_ms=exp_ms, traffic_bytes_override=traffic_bytes,
        )
        if not result:
            return None

        password = result.get("password", "")
        all_links = c.build_links_for_inbounds(chosen, result["client_id"], email, password)
        config_link = all_links[0]["link"] if all_links else c.build_vless_link(primary, result["client_id"], email, password)
        expires_at = (datetime.now() + timedelta(hours=int(duration_hours))).strftime("%Y-%m-%d %H:%M")
        return {
            "config_link": config_link,
            "config_links": all_links,
            "config_type": (primary.get("protocol", "vless") or "vless"),
            "email": email,
            "client_id": result["client_id"],
            "password": password,
            "server_id": server["id"],
            "inbound_id": primary["id"],
            "server_label": server["label"],
            "expires_at": expires_at,
            "traffic_mb": int(traffic_mb),
            "duration_hours": int(duration_hours),
        }
    except Exception:
        return None
    finally:
        await c.close()
