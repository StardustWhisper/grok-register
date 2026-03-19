#!/usr/bin/env python3
"""
临时邮箱管理器 - 保存和管理邮箱的访问密钥

功能：
1. 创建邮箱时保存 token 到本地
2. 查询已有邮箱的 token
3. 列出所有保存的邮箱
4. 清理过期的邮箱记录
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import base64
import json
from typing import Any, Dict, Optional, Tuple

from curl_cffi import requests


def _load_dotenv(path: str = ".env") -> None:
    """加载 .env 文件"""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                os.environ[key] = value
    except Exception:
        pass


_load_dotenv()

# ==========================================
# 配置
# ==========================================

EMAIL_STORAGE_FILE = ".email_tokens.json"
TEMP_MAIL_BASE = os.getenv("TEMP_MAIL_BASE", "").rstrip("/")
TEMP_MAIL_ADMIN_PASSWORD = os.getenv("TEMP_MAIL_ADMIN_PASSWORD", "").strip()
TEMP_MAIL_DOMAIN = os.getenv("TEMP_MAIL_DOMAIN", "").strip()
TEMP_MAIL_DOMAINS = [
    d.strip() for d in os.getenv("TEMP_MAIL_DOMAINS", "").split(",") if d.strip()
]


def _ssl_verify() -> bool:
    flag = os.getenv("OPENAI_SSL_VERIFY", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _decode_jwt(token: str) -> Optional[dict]:
    """
    解码 JWT token（不需要密钥，只解码 payload）
    
    Args:
        token: JWT token 字符串
        
    Returns:
        解码后的 payload 字典，失败返回 None
    """
    try:
        if not token or isinstance(token, str) and "." not in token:
            return None
        
        parts = token.split(".")
        if len(parts) != 3:
            return None
        
        payload_b64 = parts[1]
        
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        
        payload_json = base64.b64decode(payload_b64)
        return json.loads(payload_json)
    except Exception:
        return None


def _temp_mail_admin_headers(*, use_json: bool = False) -> dict:
    if not TEMP_MAIL_ADMIN_PASSWORD:
        raise RuntimeError("未设置 TEMP_MAIL_ADMIN_PASSWORD")
    headers = {"Accept": "application/json", "x-admin-auth": TEMP_MAIL_ADMIN_PASSWORD}
    if TEMP_MAIL_DOMAIN:
        headers["x-custom-auth"] = TEMP_MAIL_DOMAIN
    if use_json:
        headers["Content-Type"] = "application/json"
    return headers


def _temp_mail_domains() -> list:
    """获取临时邮箱域名列表"""
    if TEMP_MAIL_DOMAINS:
        return TEMP_MAIL_DOMAINS
    if TEMP_MAIL_DOMAIN:
        return [TEMP_MAIL_DOMAIN]
    return []


_COMMON_FIRST_NAMES = [
    "james",
    "john",
    "robert",
    "michael",
    "william",
    "david",
    "richard",
    "joseph",
    "thomas",
    "charles",
    "christopher",
    "daniel",
    "matthew",
    "anthony",
    "mark",
    "donald",
    "steven",
    "paul",
    "andrew",
    "joshua",
    "kevin",
    "brian",
    "george",
    "timothy",
    "ronald",
    "edward",
    "jason",
    "jeffrey",
    "ryan",
    "jacob",
    "gary",
    "nicholas",
    "eric",
    "jonathan",
    "stephen",
    "larry",
    "justin",
    "scott",
    "brandon",
    "benjamin",
    "samuel",
    "gregory",
    "alexander",
    "patrick",
    "frank",
    "tyler",
    "henry",
    "douglas",
    "peter",
    "nathan",
    "zachary",
    "kyle",
    "walter",
    "harold",
    "carl",
    "arthur",
    "russell",
    "phil",
    "chris",
    "andy",
    "mike",
    "rob",
    "dan",
    "matt",
    "tony",
    "steve",
    "jeff",
    "billy",
    "jim",
    "joe",
    "tom",
    "ray",
    "jack",
    "sam",
    "ben",
]

_COMMON_LAST_NAMES = [
    "smith",
    "johnson",
    "williams",
    "brown",
    "jones",
    "garcia",
    "miller",
    "davis",
    "rodriguez",
    "martinez",
    "hernandez",
    "lopez",
    "gonzalez",
    "wilson",
    "anderson",
    "thomas",
    "taylor",
    "moore",
    "jackson",
    "martin",
    "lee",
    "perez",
    "thompson",
    "white",
    "harris",
    "sanchez",
    "clark",
    "ramirez",
    "lewis",
    "robinson",
    "walker",
    "young",
    "allen",
    "king",
    "wright",
    "scott",
    "torres",
    "nguyen",
    "hill",
    "flores",
    "green",
    "adams",
    "nelson",
    "baker",
    "hall",
    "rivera",
    "campbell",
    "mitchell",
    "carter",
    "roberts",
    "gomez",
    "phillips",
    "evans",
    "turner",
    "diaz",
    "parker",
    "cruz",
    "edwards",
    "collins",
    "reyes",
    "stewart",
    "morris",
    "morgan",
    "reed",
    "cook",
    "rogers",
    "peterson",
]

_LETTER_COMBOS = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    "whiskey",
    "xray",
    "yankee",
    "zulu",
]


def _random_local_part() -> str:
    import random
    import secrets

    first = random.choice(_COMMON_FIRST_NAMES)
    last = random.choice(_COMMON_LAST_NAMES)
    year = random.randint(1975, 2004)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    mmdd = f"{month:02d}{day:02d}"
    num = random.randint(1, 9999)
    short = f"{num:02d}" if num < 100 else str(num)
    initials = f"{first[0]}{last[0]}"
    combo = random.choice(_LETTER_COMBOS)
    tail = secrets.token_hex(2)

    patterns = [
        f"{first}{last}",
        f"{first}{last}{year}",
        f"{first}{mmdd}",
        f"{first}{short}",
        f"{first}{last[0]}{short}",
        f"{initials}{year}",
        f"{combo}{short}",
        f"{first}{last}{tail}",
    ]

    return random.choice(patterns)


# ==========================================
# 邮箱存储管理
# ==========================================


class EmailStorage:
    """邮箱 token 存储管理"""

    def __init__(self, storage_file: str = EMAIL_STORAGE_FILE):
        self.storage_file = Path(storage_file)
        self.data: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """从文件加载数据"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[Warning] 加载邮箱存储失败: {e}")
                self.data = {}

    def _save(self):
        """保存数据到文件"""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Error] 保存邮箱存储失败: {e}")

    def add_email(self, email: str, token: str, metadata: Optional[dict] = None):
        """添加或更新邮箱"""
        self.data[email] = {
            "token": token,
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self._save()
        print(f"[✓] 已保存邮箱: {email}")

    def get_email(self, email: str) -> Optional[dict]:
        """获取邮箱信息"""
        if email in self.data:
            # 更新最后使用时间
            self.data[email]["last_used"] = datetime.now().isoformat()
            self._save()
            return self.data[email]
        return None

    def get_token(self, email: str) -> Optional[str]:
        """获取邮箱的 token"""
        info = self.get_email(email)
        return info["token"] if info else None

    def list_emails(self) -> list:
        """列出所有邮箱"""
        emails = []
        for email, info in self.data.items():
            emails.append(
                {
                    "email": email,
                    "created_at": info.get("created_at"),
                    "last_used": info.get("last_used"),
                }
            )
        return sorted(emails, key=lambda x: x["last_used"], reverse=True)

    def delete_email(self, email: str) -> bool:
        """删除邮箱"""
        if email in self.data:
            del self.data[email]
            self._save()
            return True
        return False

    def cleanup_old_emails(self, days: int = 30):
        """清理超过指定天数的邮箱"""
        cutoff = datetime.now() - timedelta(days=days)
        to_delete = []

        for email, info in self.data.items():
            try:
                last_used = datetime.fromisoformat(info.get("last_used", ""))
                if last_used < cutoff:
                    to_delete.append(email)
            except:
                pass

        for email in to_delete:
            self.delete_email(email)

        if to_delete:
            print(f"[✓] 已清理 {len(to_delete)} 个过期邮箱")

        return len(to_delete)


# ==========================================
# 邮箱操作
# ==========================================


def create_email(local: Optional[str] = None, proxies: Optional[Any] = None) -> tuple:
    """
    创建临时邮箱并保存 token

    Args:
        local: 邮箱前缀（如 'test123'），如果不指定则随机生成
        proxies: 代理配置

    Returns:
        (email, token) 成功返回邮箱和token，失败返回 ("", "")
    """
    import random

    domains = _temp_mail_domains()
    if not domains:
        print("[Error] 未配置临时邮箱域名")
        return "", ""

    domain = random.choice(domains)

    # 如果没有指定 local，则随机生成
    if not local:
        local = _random_local_part()

    # 构造请求地址（用于发送给 Grok）
    requested_address = f"{local}@{domain}"
    print(f"[*] 创建邮箱: {requested_address}")

    try:
        create_resp = requests.post(
            f"{TEMP_MAIL_BASE}/admin/new_address",
            headers=_temp_mail_admin_headers(use_json=True),
            json={"enablePrefix": True, "name": local, "domain": domain},
            proxies=proxies,
            impersonate="safari",
            verify=_ssl_verify(),
            timeout=15,
        )

        if create_resp.status_code != 200:
            print(f"[Error] 创建邮箱失败: {create_resp.status_code}")
            print(f"  响应: {create_resp.text[:200]}")
            return "", ""

        data = create_resp.json() if create_resp.content else {}
        server_address = str(data.get("address") or "").strip()
        token = str(data.get("jwt") or data.get("token") or "").strip()

        if not server_address or not token:
            print("[Error] 邮箱创建响应缺少必要字段")
            return "", ""

        # 使用服务器返回的地址，这通常是最准确的规范化地址
        email = server_address if server_address else requested_address

        # 保存到存储（使用最终确定的地址作为键）
        storage = EmailStorage()
        storage.add_email(
            email,
            token,
            {
                "domain": domain, 
                "local": local, 
                "created_via": "create_email",
                "requested_address": requested_address,
                "server_address": server_address
            },
        )

        print(f"[✓] 已保存邮箱: {server_address}")
        print(f"[✓] 邮箱创建成功: {email}")
        print(f"    Token: {token[:50]}...")

        return email, token

    except Exception as e:
        print(f"[Error] 创建邮箱异常: {e}")
        return "", ""


def get_email_token(email: str, proxies: Optional[Any] = None) -> Optional[str]:
    """
    获取邮箱的 token（优先从本地存储读取）

    Args:
        email: 邮箱地址
        proxies: 代理配置

    Returns:
        token 字符串，如果失败返回 None
    """
    # 先从本地存储读取
    storage = EmailStorage()
    token = storage.get_token(email)

    if token:
        print(f"[✓] 从本地存储读取 token: {email}")
        return token

    # 本地没有，尝试创建同名邮箱
    print(f"[Info] 本地存储中未找到 {email}，尝试创建同名邮箱...")

    if "@" not in email:
        print(f"[Error] 邮箱格式错误: {email}")
        return None

    local, domain = email.split("@", 1)

    try:
        create_resp = requests.post(
            f"{TEMP_MAIL_BASE}/admin/new_address",
            headers=_temp_mail_admin_headers(use_json=True),
            json={"enablePrefix": True, "name": local, "domain": domain},
            proxies=proxies,
            impersonate="safari",
            verify=_ssl_verify(),
            timeout=15,
        )

        if create_resp.status_code == 200:
            data = create_resp.json() if create_resp.content else {}
            new_email = str(data.get("address") or "").strip()
            token = str(data.get("jwt") or data.get("token") or "").strip()

            if new_email == email and token:
                # 保存到存储
                storage.add_email(
                    email,
                    token,
                    {
                        "domain": domain,
                        "local": local,
                        "created_via": "get_email_token",
                    },
                )
                print(f"[✓] 创建同名邮箱成功: {email}")
                return token
            else:
                print(f"[Warning] 创建的邮箱不匹配: {new_email} != {email}")
                return None
        elif create_resp.status_code == 400:
            # 邮箱已存在
            print(f"[Error] 邮箱 {email} 已存在，无法创建")
            print(f"[Info] 请在邮箱服务器上删除该邮箱后重试")
            return None
        else:
            print(f"[Error] 创建邮箱失败: {create_resp.status_code}")
            return None

    except Exception as e:
        print(f"[Error] 获取邮箱 token 异常: {e}")
        return None


def fetch_messages(mail_token: str, proxies: Optional[Any] = None, debug: bool = False, email_address: Optional[str] = None) -> list:
    """
    获取邮箱的邮件列表

    Args:
        mail_token: 邮箱的 JWT token
        proxies: 代理配置
        debug: 是否打印调试信息
        email_address: 邮箱地址（如果提供，直接使用；否则从 JWT 解码）

    Returns:
        邮件列表
    """
    try:
        if email_address:
            token_data = None
        else:
            token_data = _decode_jwt(mail_token)
            if not token_data:
                if debug:
                    print("[DEBUG] JWT 解码失败")
                return []
            email_address = token_data.get("address", "")
        
        if not email_address:
            if debug:
                print("[DEBUG] 邮箱地址为空")
            return []
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {mail_token}"
        }
        
        # 生成可能的地址变体（带点和不带点）
        addresses_to_try = [email_address]
        
        # 如果地址包含点号，也尝试不带点号的版本
        if "." in email_address.split("@")[0]:
            local, domain = email_address.rsplit("@", 1)
            no_dot = local.replace(".", "")
            if no_dot != local:
                addresses_to_try.append(f"{no_dot}@{domain}")
        
        all_messages = []
        
        for addr in addresses_to_try:
            if debug:
                print(f"[DEBUG] 请求 URL: {TEMP_MAIL_BASE}/api/mails")
                print(f"[DEBUG] 邮箱地址: {addr}")
            
            # 不带 address 参数尝试一次
            resp = requests.get(
                f"{TEMP_MAIL_BASE}/api/mails",
                params={"limit": 20, "offset": 0},
                headers=headers,
                proxies=proxies,
                impersonate="safari",
                verify=_ssl_verify(),
                timeout=15,
            )
            
            # 如果没查到，再带上 address 参数试试
            if resp.status_code == 200 and not (resp.json().get("results") or resp.json().get("messages") or resp.json().get("items") or (isinstance(resp.json(), list) and resp.json())):
                if debug:
                    print(f"[DEBUG] 不带 address 没查到，尝试带上 address: {addr}")
                resp = requests.get(
                    f"{TEMP_MAIL_BASE}/api/mails",
                    params={"limit": 20, "offset": 0, "address": addr},
                    headers=headers,
                    proxies=proxies,
                    impersonate="safari",
                    verify=_ssl_verify(),
                    timeout=15,
                )
            
            if debug:
                print(f"[DEBUG] 状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                
                if debug:
                    print(f"[DEBUG] 响应类型: {type(data)}")
                    if isinstance(data, dict):
                        print(f"[DEBUG] 响应键: {list(data.keys())}")
                        print(f"[DEBUG] 响应完整内容: {json.dumps(data, ensure_ascii=False)}")
                
                messages = []
                if isinstance(data, list):
                    messages = data
                elif isinstance(data, dict):
                    messages = data.get("messages") or data.get("items") or data.get("list") or data.get("data") or data.get("results") or []
                
                if debug:
                    print(f"[DEBUG] 提取到 {len(messages)} 封邮件")
                
                all_messages.extend(messages)
                
                # 如果找到邮件就不继续尝试其他地址了
                if messages:
                    break
            else:
                if debug:
                    print(f"[DEBUG] API 错误响应: {resp.text[:200]}")
        
        # 去重（基于 msg_id）
        seen_ids = set()
        unique_messages = []
        for msg in all_messages:
            msg_id = msg.get("id") or msg.get("@id")
            if msg_id and msg_id not in seen_ids:
                seen_ids.add(msg_id)
                unique_messages.append(msg)
        
        return unique_messages
        
    except Exception as e:
        if debug:
            print(f"[DEBUG] 异常: {e}")
            import traceback
            traceback.print_exc()
        print(f"[Error] 获取邮件列表失败: {e}")
    return []


def fetch_message_detail(mail_token: str, msg_id: str, proxies: Optional[Any] = None) -> Optional[dict]:
    """
    获取单封邮件的详情

    Args:
        mail_token: 邮箱的 JWT token
        msg_id: 邮件 ID
        proxies: 代理配置

    Returns:
        邮件详情
    """
    try:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {mail_token}"
        }
        
        if isinstance(msg_id, str) and msg_id.startswith("/messages/"):
            msg_id = msg_id.split("/")[-1]
    
        resp = requests.get(
            f"{TEMP_MAIL_BASE}/api/mails/{msg_id}",
            headers=headers,
            proxies=proxies,
            impersonate="safari",
            verify=_ssl_verify(),
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[Error] 获取邮件详情失败: {e}")
    return None


def extract_verification_code(content: str) -> Optional[str]:
    """
    从邮件内容提取验证码
    支持多种格式：XXX-XXX、6位数字等

    Args:
        content: 邮件内容

    Returns:
        验证码字符串，如果未找到返回 None
    """
    if not content:
        return None

    import re

    # 模式 1: Grok 格式 XXX-XXX（3位-3位字母数字混合）
    m = re.search(r"(?<![A-Z0-9-])([A-Z0-9]{3}-[A-Z0-9]{3})(?![A-Z0-9-])", content)
    if m:
        return m.group(1)

    # 模式 2: 带标签的验证码
    m = re.search(r"(?:verification code|验证码|your code)[:\s]*[<>\s]*([A-Z0-9]{3}-[A-Z0-9]{3})\b", content, re.IGNORECASE)
    if m:
        return m.group(1)

    # 模式 3: 6 位数字（排除常见编码）
    m = re.search(r"Subject:.*?(\d{6})", content)
    if m and m.group(1) != "177010":
        return m.group(1)

    # 模式 4: HTML 标签内 6 位数字
    for code in re.findall(r">\s*(\d{6})\s*<", content):
        if code != "177010":
            return code

    # 模式 5: 独立 6 位数字
    for code in re.findall(r"(?<![&#\d])(\d{6})(?![&#\d])", content):
        if code != "177010":
            return code

    return None


def _extract_mail_content(mail_data: dict) -> str:
    """
    从邮件数据中提取所有可能的文本内容
    
    Args:
        mail_data: 邮件数据字典
        
    Returns:
        合并后的文本内容
    """
    subject = str(mail_data.get("subject") or "")
    intro = str(mail_data.get("intro") or "")
    text = str(mail_data.get("text") or "")
    html = mail_data.get("html") or ""
    raw = str(mail_data.get("raw") or "")
    
    if isinstance(html, list):
        html = "\n".join(str(x) for x in html)
    
    return "\n".join([subject, intro, text, str(html), raw])


def wait_for_verification_code(mail_token: str, timeout: int = 120, proxies: Optional[Any] = None, debug: bool = False, email_address: Optional[str] = None) -> Optional[str]:
    """
    轮询邮箱等待验证码邮件

    Args:
        mail_token: 邮箱的 JWT token
        timeout: 超时时间（秒）
        proxies: 代理配置
        debug: 是否打印调试信息
        email_address: 邮箱地址（可选，如果提供则直接使用）

    Returns:
        验证码字符串，如果超时返回 None
    """
    import time

    start = time.time()
    seen_ids = set()
    first_iteration = True

    while time.time() - start < timeout:
        if first_iteration and debug:
            print("\n[DEBUG] 开始轮询邮件...")
            messages = fetch_messages(mail_token, proxies=proxies, debug=True, email_address=email_address)
            first_iteration = False
        else:
            print(".", end="", flush=True)
            messages = fetch_messages(mail_token, proxies=proxies, email_address=email_address)
            
        def _mail_sort_key(mail_data):
            created_at = str(mail_data.get("created_at") or mail_data.get("createdAt") or "")
            if created_at:
                return created_at
            return str(mail_data.get("id") or "")
        
        if isinstance(messages, list) and messages:
            messages = sorted(messages, key=_mail_sort_key, reverse=True)
        
        for msg in messages:
            if not isinstance(msg, dict):
                if debug:
                    print(f"[DEBUG] 跳过非字典消息: {type(msg)}")
                continue
            msg_id = msg.get("id") or msg.get("@id")
            if not msg_id:
                if debug:
                    print(f"[DEBUG] 消息缺少 id")
                continue
            if msg_id in seen_ids:
                if debug:
                    print(f"[DEBUG] 已处理消息 {msg_id}，跳过")
                continue
            seen_ids.add(msg_id)

            if debug:
                print(f"\n[DEBUG] 新消息 ID: {msg_id}")
                print(f"[DEBUG] 消息字段: {list(msg.keys())}")
            
            mail_data = msg
            content = _extract_mail_content(msg)
            
            if not content and msg_id:
                if debug:
                    print(f"[DEBUG] 邮件列表项内容为空，获取详情...")
                detail = fetch_message_detail(mail_token, str(msg_id), proxies=proxies)
                if detail:
                    mail_data = detail
                    content = _extract_mail_content(detail)
            
            if debug:
                print(f"[DEBUG] 提取的内容长度: {len(content)}")
                if content:
                    print(f"[DEBUG] 内容预览: {content[:500]}")
            
            if content:
                code = extract_verification_code(content)
                if code:
                    if debug:
                        print(f"[DEBUG] ✓ 找到验证码: {code}")
                    print(f"\n[✓] 验证码: {code}")
                    return code
            else:
                if debug:
                    print(f"[DEBUG] 无法提取邮件内容")
                
        if not messages and debug:
            print(f"[DEBUG] 本轮未找到邮件")
            
        time.sleep(2)
    
    print(" 超时，未收到验证码")
    return None


# ==========================================
# 适配层
# ==========================================


def get_email_and_token(local: Optional[str] = None, proxies: Optional[Any] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    创建临时邮箱并返回 (email, mail_token)

    Args:
        local: 邮箱前缀
        proxies: 代理配置

    Returns:
        (email, mail_token) 成功返回邮箱和token，失败返回 (None, None)
    """
    email, token = create_email(local=local, proxies=proxies)
    if email and token:
        return email, token
    return None, None


def get_oai_code(mail_token: str, email: Optional[str] = None, timeout: int = 30, proxies: Optional[Any] = None, debug: bool = True) -> Optional[str]:
    """
    轮询邮箱等待验证码

    Args:
        mail_token: 邮箱的 JWT token
        email: 邮箱地址（可选，用于直接查询而不是从 JWT 解码）
        timeout: 超时时间（秒）
        proxies: 代理配置
        debug: 是否打印调试信息

    Returns:
        验证码字符串，如果超时返回 None
    """
    code = wait_for_verification_code(mail_token=mail_token, timeout=timeout, proxies=proxies, email_address=email, debug=debug)
    if code:
        code = code.replace("-", "")
    return code


def list_saved_emails():
    """列出所有保存的邮箱"""
    storage = EmailStorage()
    emails = storage.list_emails()

    if not emails:
        print("[Info] 本地没有保存的邮箱")
        return

    print(f"\n[*] 已保存的邮箱 ({len(emails)} 个):")
    print("=" * 80)

    for i, info in enumerate(emails, 1):
        print(f"{i}. {info['email']}")
        print(f"   创建时间: {info['created_at']}")
        print(f"   最后使用: {info['last_used']}")
        print()


# ==========================================
# 命令行接口
# ==========================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="临时邮箱管理器")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 创建邮箱
    create_parser = subparsers.add_parser("create", help="创建新邮箱")
    create_parser.add_argument("--local", help="邮箱前缀（如 test123）")

    # 获取 token
    get_parser = subparsers.add_parser("get", help="获取邮箱 token")
    get_parser.add_argument("email", help="邮箱地址")

    # 列出邮箱
    subparsers.add_parser("list", help="列出所有保存的邮箱")

    # 清理
    cleanup_parser = subparsers.add_parser("cleanup", help="清理过期邮箱")
    cleanup_parser.add_argument(
        "--days", type=int, default=30, help="保留天数（默认30天）"
    )

    # 删除邮箱
    delete_parser = subparsers.add_parser("delete", help="删除保存的邮箱")
    delete_parser.add_argument("email", help="邮箱地址")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "create":
        email, token = create_email(local=args.local)
        if email:
            print(f"\n[✓] 邮箱创建成功!")
            print(f"    地址: {email}")
            print(f"    Token: {token}")

    elif args.command == "get":
        token = get_email_token(args.email)
        if token:
            print(f"\n[✓] Token 获取成功!")
            print(f"    邮箱: {args.email}")
            print(f"    Token: {token}")
        else:
            print(f"\n[×] 无法获取邮箱 token")
            return 1

    elif args.command == "list":
        list_saved_emails()

    elif args.command == "cleanup":
        storage = EmailStorage()
        count = storage.cleanup_old_emails(days=args.days)
        print(f"[✓] 已清理 {count} 个过期邮箱")

    elif args.command == "delete":
        storage = EmailStorage()
        if storage.delete_email(args.email):
            print(f"[✓] 已删除邮箱: {args.email}")
        else:
            print(f"[×] 邮箱不存在: {args.email}")
            return 1


if __name__ == "__main__":
    main()
