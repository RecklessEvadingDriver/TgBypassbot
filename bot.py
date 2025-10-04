#!/usr/bin/env python3
# bot.py -- Professional Unified Bypass Bot (async, python-telegram-bot v20+)
# Comprehensive bypass support for 20+ services
# Optimized for Heroku deployment
# Version: 2.1 | Last Updated: 2025-01-04

import os
import json
import re
import time
import base64
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REQUIRED_CHANNEL = "@hammerbypass"  # Channel username
CHANNEL_LINK = "https://t.me/+D0ohqup8BxE2NWRl"  # Channel invite link
GROUP_LINK = "https://t.me/+D0ohqup8BxE2NWRl"  # Group link (same as channel)

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable not set!")
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID environment variable not set!")

STORE_FILE = "store.json"
DEFAULT_DOMAINS = {
    "hubdrive": "https://hubdrive.wales/",
    "hubcloud": "https://hubcloud.one/",
    "hubcdn": "https://hubcdn.fans",
    "gdflix": "https://new.gdflix.net/",
    "photolinx": "https://photolinx.space",
    "gofile": "https://gofile.io",
    "driveleech": "https://driveleech.net",
    "driveseed": "https://driveseed.org",
    "vcloud": "https://vcloud.lol",
    "fastdl": "https://fastdlserver.lol",
    "linkstore": "https://linkstore.rest",
    "luxdrive": "https://new7.luxedrive.space",
    "howblogs": "https://howblogs.xyz",
    "vifix": "https://vifix.site",
    "ziddiflix": "https://ziddiflix.com",
    "fastlinks": "https://fastilinks.online",
    "wlinkfast": "https://wlinkfast.store",
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"

print(f"🤖 Bot Starting...")
print(f"👤 Admin ID: {ADMIN_ID}")
print(f"📢 Required Channel: {REQUIRED_CHANNEL}")
print(f"🔗 Group Link: {GROUP_LINK}")
print(f"🕐 UTC Time: 2025-01-04 15:08:24")

# ---------------- Persistence ----------------
def load_store():
    if not os.path.exists(STORE_FILE):
        s = {"allowed_users": [], "allowed_chats": [], "domains": {}}
        with open(STORE_FILE, "w") as f:
            json.dump(s, f)
        return s
    try:
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading store: {e}")
        return {"allowed_users": [], "allowed_chats": [], "domains": {}}

def save_store(store):
    try:
        with open(STORE_FILE, "w") as f:
            json.dump(store, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving store: {e}")

STORE = load_store()
DOMAINS = DEFAULT_DOMAINS.copy()
DOMAINS.update(STORE.get("domains", {}))

# ---------------- Executor ----------------
EXECUTOR = ThreadPoolExecutor(max_workers=10)

async def run_blocking(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(EXECUTOR, partial(fn, *args, **kwargs))

# ---------------- Helpers ----------------
def is_admin(uid: int) -> bool:
    return int(uid) == int(ADMIN_ID)

async def check_channel_membership(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if user is member of required channel"""
    if is_admin(user_id):
        return True
    
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except BadRequest as e:
        print(f"⚠️ Error checking membership for {user_id}: {e}")
        # If channel is private or not found, allow access
        return True
    except Exception as e:
        print(f"❌ Unexpected error checking membership: {e}")
        return True

def escape_markdown(s: str) -> str:
    if s is None:
        return ""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = str(s)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    return result

def build_inline_buttons(links: list):
    """Build inline keyboard with download links"""
    if not links:
        return None
    
    buttons = []
    for item in links[:20]:
        typ = item.get("type", "Download")
        url = item.get("url", "")
        if not url:
            continue
        
        emoji = "📥"
        if "direct" in typ.lower() or "instant" in typ.lower():
            emoji = "⚡"
        elif "cloud" in typ.lower():
            emoji = "☁️"
        elif "pixeldrain" in typ.lower():
            emoji = "🎯"
        elif "gofile" in typ.lower():
            emoji = "📦"
        elif "drive" in typ.lower() or "drivebot" in typ.lower():
            emoji = "💾"
        elif "index" in typ.lower():
            emoji = "📂"
        
        buttons.append([InlineKeyboardButton(f"{emoji} {typ}", url=url)])
    
    return InlineKeyboardMarkup(buttons) if buttons else None

def build_message(file_name: str, file_size: str, links: list, service: str = "") -> str:
    """Build professional message text"""
    lines = []
    if service:
        lines.append(f"*🔓 {escape_markdown(service)} Bypass Result*\n")
    else:
        lines.append("*🔓 Bypass Result*\n")
    
    if file_name:
        lines.append(f"📄 *File:* `{escape_markdown(file_name)}`")
    if file_size:
        lines.append(f"📊 *Size:* `{escape_markdown(file_size)}`")
    
    if links:
        lines.append(f"🔗 *Links Found:* `{len(links)}`")
        lines.append("\n_Click the buttons below to download:_")
    else:
        lines.append("\n⚠️ _No downloadable links found\\._")
    
    return "\n".join(lines)

# ---------------- Decoders ----------------
def rot13(s: str) -> str:
    return ''.join(
        chr((ord(c) - (65 if c.isupper() else 97) + 13) % 26 + (65 if c.isupper() else 97)) if c.isalpha() else c
        for c in s
    )

def try_decode_chain(enc: str):
    try:
        step = base64.b64decode(enc).decode()
        step = base64.b64decode(step).decode()
        step = rot13(step)
        step = base64.b64decode(step).decode()
        return json.loads(step)
    except Exception:
        return None

def base64_decode_safe(s: str) -> str:
    try:
        return base64.b64decode(s).decode('utf-8')
    except Exception:
        return ""

def get_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

# ---------------- Bypass Implementations (Same as before) ----------------

def hubdrive_bypass(url: str):
    """HubDrive bypass"""
    try:
        headers = {"Referer": DOMAINS.get("hubdrive"), "User-Agent": USER_AGENT}
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        link_elem = soup.select_one('.btn.btn-primary.btn-user.btn-success1.m-1')
        if link_elem:
            href = link_elem.get('href')
            if href:
                return {"file_name": "", "file_size": "", "links": [{"type": "Direct Link", "url": href}]}
        
        patterns = [
            r"https:\/\/hubcloud\.one\/drive\/[a-zA-Z0-9]+",
            r"https:\/\/cdn\.fsl-buckets\.xyz\/[^\s\"'<>]+",
            r"https:\/\/pixeldrain\.dev\/api\/file\/[^\s\"'<>]+",
        ]
        for pat in patterns:
            m = re.search(pat, r.text, re.IGNORECASE)
            if m:
                return {"file_name": "", "file_size": "", "links": [{"type": "Direct Link", "url": m.group(0)}]}
        
        return {"file_name": "", "file_size": "", "links": []}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def hubcloud_bypass(url: str):
    """HubCloud bypass"""
    try:
        base_url = "https://hubcloud.one"
        new_url = url.replace(get_base_url(url), base_url)
        headers = {"User-Agent": USER_AGENT}
        
        doc = requests.get(new_url, headers=headers, timeout=20).text
        soup = BeautifulSoup(doc, 'html.parser')
        
        script_tag = soup.find('script', string=re.compile(r'var\s+url'))
        link = ""
        
        if script_tag:
            match = re.search(r"var url = '([^']*)'", script_tag.string)
            if match:
                link = match.group(1)
        
        if not link:
            center_link = soup.select_one("div.vd > center > a")
            if center_link:
                link = center_link.get('href', '')
        
        if not link.startswith("https://"):
            link = base_url + link
        
        document = requests.get(link, headers=headers, timeout=20).text
        soup2 = BeautifulSoup(document, 'html.parser')
        
        header = soup2.select_one("div.card-header")
        file_name = header.get_text(strip=True) if header else ""
        size_elem = soup2.select_one("i#size")
        file_size = size_elem.get_text(strip=True) if size_elem else ""
        
        links = []
        card_body = soup2.select_one("div.card-body")
        if card_body:
            for anchor in card_body.select("h2 a.btn"):
                href = anchor.get('href', '')
                text = anchor.get_text(strip=True)
                
                if "Download [FSL Server]" in text:
                    links.append({"type": "FSL Server", "url": href})
                elif "Download File" in text or "Download [Server : 1]" in text:
                    links.append({"type": "Direct Download", "url": href})
                elif "pixeldra" in href:
                    links.append({"type": "Pixeldrain", "url": href})
                elif "Download [Server : 10Gbps]" in text:
                    try:
                        loc = requests.get(href, headers=headers, allow_redirects=False, timeout=15).headers.get("location", "")
                        if "link=" in loc:
                            links.append({"type": "10Gbps Server", "url": loc.split("link=")[-1]})
                    except:
                        pass
        
        return {"file_name": file_name, "file_size": file_size, "links": links}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def hubcdn_bypass(url: str):
    """HubCDN bypass"""
    try:
        headers = {"User-Agent": USER_AGENT}
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        script_tag = soup.find('script', string=re.compile(r'var\s+reurl'))
        if script_tag:
            reurl_match = re.search(r'reurl\s*=\s*"([^"]+)"', script_tag.string)
            if reurl_match:
                reurl = reurl_match.group(1)
                if '?r=' in reurl:
                    encoded_url = reurl.split('?r=')[-1]
                    decoded_url = base64_decode_safe(encoded_url)
                    if 'link=' in decoded_url:
                        final_url = unquote(decoded_url.split('link=')[-1])
                        return {"file_name": "", "file_size": "", "links": [{"type": "Direct Link", "url": final_url}]}
        
        return {"file_name": "", "file_size": "", "links": []}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def vcloud_bypass(url: str):
    """VCloud bypass"""
    try:
        headers = {"User-Agent": USER_AGENT}
        
        if "api/index.php" in url:
            doc = requests.get(url, headers=headers, timeout=20).text
            soup = BeautifulSoup(doc, 'html.parser')
            new_link = soup.select_one("div.main h4 a")
            if new_link:
                url = new_link.get('href', '')
        
        doc = requests.get(url, headers=headers, timeout=20).text
        soup = BeautifulSoup(doc, 'html.parser')
        
        script_tag = soup.find('script', string=re.compile(r'var\s+url'))
        if not script_tag:
            return {"file_name": "", "file_size": "", "links": []}
        
        url_match = re.search(r"var url = '([^']*)'", script_tag.string)
        if not url_match:
            return {"file_name": "", "file_size": "", "links": []}
        
        url_value = url_match.group(1)
        document = requests.get(url_value, headers=headers, timeout=20).text
        soup2 = BeautifulSoup(document, 'html.parser')
        
        header = soup2.select_one("div.card-header")
        file_name = header.get_text(strip=True) if header else ""
        size_elem = soup2.select_one("i#size")
        file_size = size_elem.get_text(strip=True) if size_elem else ""
        
        links = []
        card_body = soup2.select_one("div.card-body")
        if card_body:
            for anchor in card_body.select("h2 a.btn"):
                href = anchor.get('href', '')
                text = anchor.get_text(strip=True)
                
                if "Download [FSL Server]" in text:
                    links.append({"type": "FSL Server", "url": href})
                elif "Download [Server : 1]" in text:
                    links.append({"type": "Direct Download", "url": href})
                elif "pixeldra" in href:
                    links.append({"type": "Pixeldrain", "url": href})
        
        return {"file_name": file_name, "file_size": file_size, "links": links}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

class GDFlixBypass:
    def __init__(self):
        self.session = requests.Session()
        self.base = DOMAINS.get("gdflix", DEFAULT_DOMAINS["gdflix"])

    def bypass(self, url: str):
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            
            file_name = ""
            file_size = ""
            for li in soup.select("ul > li.list-group-item"):
                txt = li.get_text(separator=" ", strip=True)
                if "Name" in txt:
                    file_name = txt.split(":")[-1].strip()
                if "Size" in txt:
                    file_size = txt.split(":")[-1].strip()
            
            links = []
            for a in soup.select("div.text-center a"):
                text = a.get_text(strip=True)
                href = a.get("href")
                if not href:
                    continue
                if href.startswith("/"):
                    href = urljoin(self.base, href)
                
                if "Instant DL" in text:
                    try:
                        r2 = self.session.get(href, allow_redirects=False, timeout=15)
                        link = r2.headers.get("location", href)
                        if "url=" in link:
                            link = link.split("url=")[-1]
                        links.append({"type": "Instant Download", "url": link})
                    except:
                        pass
                elif "DIRECT DL" in text:
                    links.append({"type": "Direct Download", "url": href})
                elif "CLOUD DOWNLOAD" in text:
                    links.append({"type": "Cloud Download", "url": href})
                elif "PixelDrain" in text:
                    links.append({"type": "Pixeldrain", "url": href})
                elif "GoFile" in text:
                    links.append({"type": "GoFile", "url": href})
            
            seen = set()
            uniq = []
            for l in links:
                u = l.get("url")
                if not u or u in seen:
                    continue
                seen.add(u)
                uniq.append(l)
            
            return {"file_name": file_name, "file_size": file_size, "links": uniq}
        except Exception as e:
            return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

class PhotoLinxBypass:
    def __init__(self):
        self.base = DOMAINS.get("photolinx", DEFAULT_DOMAINS["photolinx"])
        self.session = requests.Session()

    def bypass(self, url: str):
        try:
            r = self.session.get(url, timeout=15)
            ssid = self.session.cookies.get("PHPSESSID")
            if not ssid:
                return {"file_name": "", "file_size": "", "links": [], "error": "no PHPSESSID"}
            
            soup = BeautifulSoup(r.text, "html.parser")
            file_name = soup.select_one("h1").text.strip() if soup.select_one("h1") else ""
            gen = soup.select_one("#generate_url")
            if not gen:
                return {"file_name": file_name, "file_size": "", "links": [], "error": "no generate button"}
            
            access_token = gen.get("data-token")
            uid = gen.get("data-uid")
            body = {"type": "DOWNLOAD_GENERATE", "payload": {"access_token": access_token, "uid": uid}}
            headers = {
                "cookie": f"PHPSESSID={ssid}",
                "Referer": url,
                "x-requested-with": "XMLHttpRequest",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": USER_AGENT
            }
            action_url = f"{self.base}/action"
            r2 = self.session.post(action_url, json=body, headers=headers, timeout=15)
            if r2.status_code != 200:
                return {"file_name": file_name, "file_size": "", "links": [], "error": f"failed_{r2.status_code}"}
            
            data = r2.json()
            dw = data.get("download_url")
            if not dw:
                return {"file_name": file_name, "file_size": "", "links": [], "error": "no download_url"}
            
            return {"file_name": file_name, "file_size": "", "links": [{"type": "Direct Download", "url": dw}]}
        except Exception as e:
            return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

class GoFileBypass:
    def bypass(self, url: str):
        try:
            file_id = urlparse(url).path.strip("/").split("/")[-1]
            if "?c=" in url:
                file_id = parse_qs(urlparse(url).query).get('c', [file_id])[0]
            
            r = requests.post("https://api.gofile.io/accounts", data={}, timeout=15)
            r.raise_for_status()
            token = r.json().get("data", {}).get("token")
            
            global_js = requests.get("https://gofile.io/dist/js/global.js", timeout=15).text
            wt_match = re.search(r'''appdata\.wt\s*=\s*['"]([^'"]+)['"]''', global_js)
            wt = wt_match.group(1) if wt_match else "4fd6sg89d7s6"
            
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            params = {"wt": wt}
            r2 = requests.get(f"https://api.gofile.io/contents/{file_id}", headers=headers, params=params, timeout=15)
            r2.raise_for_status()
            
            j = r2.json()
            children = j.get("data", {}).get("children", {})
            if not children:
                return {"file_name": "", "file_size": "", "links": [], "error": "no children"}
            
            first_key = list(children.keys())[0]
            child_data = children[first_key]
            link = child_data.get("link")
            file_name = child_data.get("name", "")
            size = child_data.get("size", 0)
            
            if size < 1024 * 1024 * 1024:
                file_size = f"{size / (1024 * 1024):.2f} MB"
            else:
                file_size = f"{size / (1024 * 1024 * 1024):.2f} GB"
            
            return {"file_name": file_name, "file_size": file_size, "links": [{"type": "Direct Download", "url": link}], "token": token}
        except Exception as e:
            return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

class DriveLeechBypass:
    def __init__(self):
        self.user_agent = USER_AGENT
        self.session = requests.Session()

    def bypass(self, url: str):
        try:
            parsed = urlparse(url)
            base_domain = f"{parsed.scheme}://{parsed.netloc}"
            
            if "driveleech" in base_domain:
                referer = DOMAINS.get("driveleech")
            else:
                referer = DOMAINS.get("driveseed")
            
            headers = {"Referer": referer, "User-Agent": self.user_agent}
            
            if "r?key=" in url:
                response = self.session.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(response.text, 'html.parser')
                script_tag = soup.find('script')
                if script_tag:
                    replace_match = re.search(r'replace\("([^"]+)"\)', script_tag.string or "")
                    if replace_match:
                        url = base_domain + replace_match.group(1)
            
            response = self.session.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            file_name = ""
            file_size = ""
            for li in soup.select("ul > li.list-group-item"):
                text = li.get_text(strip=True)
                if "Name :" in text:
                    file_name = text.split("Name :")[-1].strip()
                if "Size :" in text:
                    file_size = text.split("Size :")[-1].strip()
            
            links = []
            for anchor in soup.select("div.text-center > a"):
                text = anchor.get_text(strip=True)
                href = anchor.get('href', '')
                
                if "Instant Download" in text:
                    try:
                        parsed_url = urlparse(href)
                        api_url = f"{parsed_url.scheme}://{parsed_url.netloc}/api"
                        keys = parse_qs(parsed_url.query).get('url')
                        
                        if keys:
                            data = {'keys': keys}
                            api_response = self.session.post(api_url, headers=headers, data=data, timeout=20)
                            result = api_response.json()
                            video_url = result.get('url')
                            if video_url:
                                links.append({"type": "Instant Download", "url": video_url})
                    except:
                        pass
                elif "Cloud Download" in text:
                    links.append({"type": "Cloud Download", "url": href})
            
            return {"file_name": file_name, "file_size": file_size, "links": links}
        except Exception as e:
            return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def linkstore_bypass(url: str):
    try:
        headers = {"User-Agent": USER_AGENT}
        doc = requests.get(url, headers=headers, timeout=20).text
        soup = BeautifulSoup(doc, 'html.parser')
        links = []
        for anchor in soup.select("a.ep-simple-button"):
            href = anchor.get('href', '')
            if href:
                links.append({"type": "Download", "url": href})
        return {"file_name": "", "file_size": "", "links": links}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def luxdrive_bypass(url: str):
    try:
        headers = {"User-Agent": USER_AGENT}
        doc = requests.get(url, headers=headers, timeout=20).text
        soup = BeautifulSoup(doc, 'html.parser')
        links = []
        for anchor in soup.select("div > div > a"):
            href = anchor.get('href', '')
            if href:
                if ".mkv" in href or ".mp4" in href:
                    links.append({"type": "Instant Download", "url": href})
                else:
                    links.append({"type": "Download", "url": href})
        return {"file_name": "", "file_size": "", "links": links}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def vifix_bypass(url: str):
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, allow_redirects=False, timeout=20)
        location = response.headers.get("location", "")
        if location:
            return {"file_name": "", "file_size": "", "links": [{"type": "Redirect Link", "url": location}]}
        return {"file_name": "", "file_size": "", "links": []}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def howblogs_bypass(url: str):
    try:
        headers = {"User-Agent": USER_AGENT}
        doc = requests.get(url, headers=headers, timeout=20).text
        soup = BeautifulSoup(doc, 'html.parser')
        links = []
        for anchor in soup.select("div.center_it a"):
            href = anchor.get('href', '')
            if href:
                links.append({"type": "Download", "url": href})
        return {"file_name": "", "file_size": "", "links": links}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def fastdl_bypass(url: str):
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, allow_redirects=False, timeout=20)
        location = response.headers.get("location", "")
        if location:
            return {"file_name": "", "file_size": "", "links": [{"type": "Direct Link", "url": location}]}
        return {"file_name": "", "file_size": "", "links": []}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def fastlinks_bypass(url: str):
    try:
        session = requests.Session()
        headers = {"User-Agent": USER_AGENT}
        res = session.get(url, headers=headers, timeout=20)
        ssid = session.cookies.get("PHPSESSID", "")
        form_data = {"_csrf_token_645a83a41868941e4692aa31e7235f2": "3000f5248d9d207e4941e0aa053e1bcfd04dcbab"}
        cookies = {"PHPSESSID": ssid}
        doc = session.post(url, data=form_data, cookies=cookies, headers=headers, timeout=20).text
        soup = BeautifulSoup(doc, 'html.parser')
        links = []
        for anchor in soup.select("div.well > a"):
            href = anchor.get('href', '')
            if href:
                links.append({"type": "Download", "url": href})
        return {"file_name": "", "file_size": "", "links": links}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

def wlinkfast_bypass(url: str):
    try:
        headers = {"User-Agent": USER_AGENT}
        doc = requests.get(url, headers=headers, timeout=20).text
        soup = BeautifulSoup(doc, 'html.parser')
        h1_link = soup.select_one("h1 > a")
        if not h1_link:
            return {"file_name": "", "file_size": "", "links": []}
        link = h1_link.get('href', '')
        if not link:
            return {"file_name": "", "file_size": "", "links": []}
        doc2 = requests.get(link, headers=headers, timeout=20).text
        soup2 = BeautifulSoup(doc2, 'html.parser')
        download_btn = soup2.select_one("a#downloadButton")
        download_link = ""
        if download_btn:
            download_link = download_btn.get('href', '')
        if not download_link:
            script_match = re.search(r'''window\.location\.href\s*=\s*['"]([^'"]+)['"]''', doc2)
            if script_match:
                download_link = script_match.group(1)
        if download_link:
            return {"file_name": "", "file_size": "", "links": [{"type": "Download", "url": download_link}]}
        return {"file_name": "", "file_size": "", "links": []}
    except Exception as e:
        return {"file_name": "", "file_size": "", "links": [], "error": str(e)}

# ---------------- Telegram Handlers ----------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Check if it's a private chat
    if chat.type == "private":
        # Check channel membership
        is_member = await check_channel_membership(context, user.id)
        
        if not is_member:
            # User hasn't joined the channel
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ Verify Membership", callback_data="verify_membership")]
            ])
            
            not_member_text = f"""
*🔐 Channel Membership Required*

Hello {escape_markdown(user.first_name)}\\! 👋

To use this bot, you must first join our official channel:

*📢 Channel:* {escape_markdown(REQUIRED_CHANNEL)}
[Click here to join]({escape_markdown(CHANNEL_LINK)})

*Why join\\?*
✅ Get access to bypass features
✅ Stay updated with new services
✅ Access 20\\+ file hosting services
✅ Fast and reliable extraction

*After joining, click "✅ Verify Membership" below\\.*

_This is a one\\-time verification\\._
"""
            await update.message.reply_text(
                not_member_text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
        else:
            # User has joined the channel
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Join Group to Use Bot", url=GROUP_LINK)]
            ])
            
            member_text = f"""
*✅ Verification Successful\\!*

Hello {escape_markdown(user.first_name)}\\! 🎉

You have successfully joined our channel\\. Thank you\\!

*📍 Important:*
This bot works exclusively in our group\\.

*🔗 Join Our Group:*
Click the button below to join the group where you can use all bypass commands\\.

[Join Group]({escape_markdown(GROUP_LINK)})

*📋 In the group, use:*
• `/bypass <url>` \\- Auto\\-detect and bypass
• Or use specific service commands
• Type `/help` in group for all commands

*⚡ Supported Services:*
HubDrive • HubCloud • HubCDN • VCloud
GDFlix • PhotoLinx • GoFile • DriveLeech
DriveSeed • Linkstore • Luxdrive \\& more\\!

_See you in the group\\!_ 💪
"""
            await update.message.reply_text(
                member_text,
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
    else:
        # It's a group chat
        group_welcome_text = f"""
*🤖 Professional Bypass Bot*

Hello {escape_markdown(user.first_name)}\\! 👋

*🎯 Quick Start:*
• `/bypass <url>` \\- Auto\\-detect and bypass any link
• Or use specific commands like `/hubdrive`, `/gdflix`, etc\\.

*🔓 Supported Services \\(20\\+\\):*
`HubDrive` • `HubCloud` • `HubCDN` • `VCloud`
`GDFlix` • `PhotoLinx` • `GoFile` • `DriveLeech`
`DriveSeed` • `Linkstore` • `Luxdrive` • `Vifix`
`FastDL` • `FastLinks` • `WLinkFast` \\& more\\!

*📚 Commands:*
• `/help` \\- View all commands
• `/services` \\- List all supported services

*⚡ Features:*
✅ Instant link extraction
✅ Multiple download servers
✅ File info \\(name \\& size\\)
✅ Professional inline buttons

_Ready to bypass\\! Just send a command\\._
"""
        await update.message.reply_text(group_welcome_text, parse_mode="MarkdownV2")

async def verify_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verify membership button click"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    # Check channel membership
    is_member = await check_channel_membership(context, user.id)
    
    if is_member:
        # Verified successfully
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Join Group to Use Bot", url=GROUP_LINK)]
        ])
        
        success_text = f"""
*✅ Verification Successful\\!*

Welcome {escape_markdown(user.first_name)}\\! 🎉

You have successfully joined our channel\\!

*📍 Important:*
This bot works exclusively in our group\\.

*🔗 Join Our Group:*
Click the button below to join the group where you can use all bypass commands\\.

[Join Group]({escape_markdown(GROUP_LINK)})

*📋 In the group, use:*
• `/bypass <url>` \\- Auto\\-detect and bypass
• Or use specific service commands
• Type `/help` in group for all commands

*⚡ Supported Services:*
HubDrive • HubCloud • HubCDN • VCloud
GDFlix • PhotoLinx • GoFile • DriveLeech
DriveSeed • Linkstore • Luxdrive \\& more\\!

_See you in the group\\!_ 💪
"""
        await query.edit_message_text(
            success_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    else:
        # Still not a member
        error_text = f"""
*❌ Verification Failed*

{escape_markdown(user.first_name)}, you haven't joined the channel yet\\.

*Please follow these steps:*
1\\. Click the "Join Channel" button below
2\\. Join the channel {escape_markdown(REQUIRED_CHANNEL)}
3\\. Come back and click "Verify Membership" again

_Make sure you actually join the channel before clicking verify\\!_
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("🔄 Try Again", callback_data="verify_membership")]
        ])
        await query.edit_message_text(
            error_text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    chat = update.effective_chat
    
    # Only work in groups
    if chat.type == "private":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Group", url=GROUP_LINK)]])
        await update.message.reply_text(
            f"ℹ️ This bot works in group only\\!\n\n[Click here to join the group]({escape_markdown(GROUP_LINK)})",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        return
    
    help_text = """
*📚 Bot Commands & Usage*

*⚡ Bypass Commands:*
• `/bypass <url>` \\- Auto\\-detect service
• `/hubdrive <url>` • `/hubcloud <url>`
• `/hubcdn <url>` • `/vcloud <url>`
• `/gdflix <url>` • `/photolinx <url>`
• `/gofile <url>` • `/driveleech <url>`
• `/driveseed <url>` • `/linkstore <url>`
• `/luxdrive <url>` • `/vifix <url>`
• `/fastdl <url>` • `/fastlinks <url>`
• `/wlinkfast <url>` • `/howblogs <url>`

*ℹ️ Information:*
• `/help` \\- Show this message
• `/services` \\- List all supported services
• `/about` \\- About this bot

*💡 Usage Tips:*
✓ Send link with command in this group
✓ Works with 20\\+ different services
✓ Multiple servers when available
✓ Automatic quality detection
✓ Professional inline buttons

_Need help\\? Contact admin\\!_
"""
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def services_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of supported services"""
    chat = update.effective_chat
    
    # Only work in groups
    if chat.type == "private":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Group", url=GROUP_LINK)]])
        await update.message.reply_text(
            f"ℹ️ This bot works in group only\\!\n\n[Click here to join the group]({escape_markdown(GROUP_LINK)})",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        return
    
    services_text = """
*🌐 Supported Bypass Services*

*📁 Cloud Storage:*
• HubDrive • HubCloud • HubCDN
• VCloud • GDFlix • DriveLeech
• DriveSeed • Linkstore • Luxdrive

*🔗 Link Shorteners:*
• Vifix • Ziddiflix • FastDL
• FastLinks • WLinkFast • Howblogs

*📦 File Hosts:*
• GoFile • PhotoLinx • Pixeldrain
• Index Links • Direct Links

*⚡ Total Services:* `20\\+`

*🆕 Features:*
✅ Multiple download servers
✅ Instant link extraction
✅ File size \\& name detection
✅ Auto\\-service detection
✅ Professional inline buttons

_More services added regularly\\!_
"""
    await update.message.reply_text(services_text, parse_mode="MarkdownV2")

async def about_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show about information"""
    about_text = f"""
*ℹ️ About This Bot*

*🤖 Professional Bypass Bot*
_Version:_ 2\\.1
_Last Updated:_ 2025\\-01\\-04

*📊 Statistics:*
• 20\\+ Bypass Services
• Multiple Server Support
• Instant Extraction
• Professional UI

*👨‍💻 Developer:*
@{escape_markdown("RecklessEvadingDriver")}

*🔗 Channel:*
{escape_markdown(REQUIRED_CHANNEL)}
[Join Channel]({escape_markdown(CHANNEL_LINK)})

*💬 Group:*
[Join Group]({escape_markdown(GROUP_LINK)})

*⚙️ Technology:*
• Python 3\\.11\\+
• python\\-telegram\\-bot v20\\+
• Advanced extraction algorithms
• Multi\\-threaded processing

*📝 License:*
For educational purposes only\\.
Use responsibly\\.

_Thank you for using our service\\!_ ❤️
"""
    await update.message.reply_text(
        about_text,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )

# Admin handlers
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    stats_text = f"""
*📊 Bot Statistics*

*👥 Users:* `{len(STORE.get('allowed_users', []))}`
*💬 Chats:* `{len(STORE.get('allowed_chats', []))}`
*🌐 Services:* `{len(DOMAINS)}`
*📁 Store Size:* `{os.path.getsize(STORE_FILE) if os.path.exists(STORE_FILE) else 0}` bytes

*⚙️ Config:*
Admin ID: `{ADMIN_ID}`
Channel: `{escape_markdown(REQUIRED_CHANNEL)}`
Group: `{escape_markdown(GROUP_LINK)}`

_System operational ✅_
"""
    await update.message.reply_text(stats_text, parse_mode="MarkdownV2")

# Generic bypass command
async def generic_bypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, service_name: str, bypass_func):
    chat = update.effective_chat
    
    # Only work in groups
    if chat.type == "private":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Group", url=GROUP_LINK)]])
        await update.message.reply_text(
            f"ℹ️ This bot works in group only\\!\n\n[Click here to join the group]({escape_markdown(GROUP_LINK)})",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        return
    
    if not context.args:
        await update.message.reply_text(f"*Usage:* `/{service_name.lower()} <url>`", parse_mode="MarkdownV2")
        return
    
    url = context.args[0].strip()
    status_msg = await update.message.reply_text(f"⏳ Processing {escape_markdown(service_name)}\\.\\.\\.", parse_mode="MarkdownV2")
    
    res = await run_blocking(bypass_func, url)
    msg = build_message(res.get("file_name", ""), res.get("file_size", ""), res.get("links", []), service_name)
    keyboard = build_inline_buttons(res.get("links", []))
    
    if res.get("error"):
        msg += f"\n\n⚠️ _Error: {escape_markdown(res.get('error'))}_"
    if res.get("token"):
        msg += f"\n\n🔑 `accountToken={escape_markdown(res.get('token'))}`"
    
    await status_msg.edit_text(msg, parse_mode="MarkdownV2", reply_markup=keyboard)

# Command handlers
async def cmd_hubdrive(u, c): await generic_bypass_cmd(u, c, "HubDrive", hubdrive_bypass)
async def cmd_hubcloud(u, c): await generic_bypass_cmd(u, c, "HubCloud", hubcloud_bypass)
async def cmd_hubcdn(u, c): await generic_bypass_cmd(u, c, "HubCDN", hubcdn_bypass)
async def cmd_vcloud(u, c): await generic_bypass_cmd(u, c, "VCloud", vcloud_bypass)
async def cmd_gdflix(u, c): await generic_bypass_cmd(u, c, "GDFlix", lambda url: GDFlixBypass().bypass(url))
async def cmd_photolinx(u, c): await generic_bypass_cmd(u, c, "PhotoLinx", lambda url: PhotoLinxBypass().bypass(url))
async def cmd_gofile(u, c): await generic_bypass_cmd(u, c, "GoFile", lambda url: GoFileBypass().bypass(url))
async def cmd_driveleech(u, c): await generic_bypass_cmd(u, c, "DriveLeech", lambda url: DriveLeechBypass().bypass(url))
async def cmd_driveseed(u, c): await generic_bypass_cmd(u, c, "DriveSeed", lambda url: DriveLeechBypass().bypass(url))
async def cmd_linkstore(u, c): await generic_bypass_cmd(u, c, "Linkstore", linkstore_bypass)
async def cmd_luxdrive(u, c): await generic_bypass_cmd(u, c, "Luxdrive", luxdrive_bypass)
async def cmd_vifix(u, c): await generic_bypass_cmd(u, c, "Vifix", vifix_bypass)
async def cmd_howblogs(u, c): await generic_bypass_cmd(u, c, "Howblogs", howblogs_bypass)
async def cmd_fastdl(u, c): await generic_bypass_cmd(u, c, "FastDL", fastdl_bypass)
async def cmd_fastlinks(u, c): await generic_bypass_cmd(u, c, "FastLinks", fastlinks_bypass)
async def cmd_wlinkfast(u, c): await generic_bypass_cmd(u, c, "WLinkFast", wlinkfast_bypass)

# Auto-detect bypass
async def bypass_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    
    # Only work in groups
    if chat.type == "private":
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Group", url=GROUP_LINK)]])
        await update.message.reply_text(
            f"ℹ️ This bot works in group only\\!\n\n[Click here to join the group]({escape_markdown(GROUP_LINK)})",
            parse_mode="MarkdownV2",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        return
    
    if not context.args:
        await update.message.reply_text("*Usage:* `/bypass <url>`", parse_mode="MarkdownV2")
        return
    
    url = context.args[0].strip()
    low = url.lower()
    status_msg = await update.message.reply_text("🔍 Detecting service\\.\\.\\.", parse_mode="MarkdownV2")
    
    # Auto-detect
    if "hubdrive" in low:
        res = await run_blocking(hubdrive_bypass, url)
        service = "HubDrive"
    elif "hubcloud" in low:
        res = await run_blocking(hubcloud_bypass, url)
        service = "HubCloud"
    elif "hubcdn" in low:
        res = await run_blocking(hubcdn_bypass, url)
        service = "HubCDN"
    elif "vcloud" in low:
        res = await run_blocking(vcloud_bypass, url)
        service = "VCloud"
    elif "gdflix" in low or "gdlink" in low:
        res = await run_blocking(lambda u: GDFlixBypass().bypass(u), url)
        service = "GDFlix"
    elif "photolinx" in low:
        res = await run_blocking(lambda u: PhotoLinxBypass().bypass(u), url)
        service = "PhotoLinx"
    elif "gofile" in low:
        res = await run_blocking(lambda u: GoFileBypass().bypass(u), url)
        service = "GoFile"
    elif "driveleech" in low:
        res = await run_blocking(lambda u: DriveLeechBypass().bypass(u), url)
        service = "DriveLeech"
    elif "driveseed" in low:
        res = await run_blocking(lambda u: DriveLeechBypass().bypass(u), url)
        service = "DriveSeed"
    elif "linkstore" in low:
        res = await run_blocking(linkstore_bypass, url)
        service = "Linkstore"
    elif "luxdrive" in low:
        res = await run_blocking(luxdrive_bypass, url)
        service = "Luxdrive"
    elif "vifix" in low or "ziddiflix" in low:
        res = await run_blocking(vifix_bypass, url)
        service = "Vifix"
    elif "howblogs" in low:
        res = await run_blocking(howblogs_bypass, url)
        service = "Howblogs"
    elif "fastdl" in low:
        res = await run_blocking(fastdl_bypass, url)
        service = "FastDL"
    elif "fastilinks" in low or "fastlinks" in low:
        res = await run_blocking(fastlinks_bypass, url)
        service = "FastLinks"
    elif "wlinkfast" in low:
        res = await run_blocking(wlinkfast_bypass, url)
        service = "WLinkFast"
    else:
        res = await run_blocking(hubdrive_bypass, url)
        service = "Auto"
        if not res.get("links"):
            res = await run_blocking(hubcloud_bypass, url)
    
    if not res.get("links"):
        await status_msg.edit_text("❌ *Bypass Failed*\n\n_Could not extract links\\._", parse_mode="MarkdownV2")
        return
    
    msg = build_message(res.get("file_name", ""), res.get("file_size", ""), res.get("links", []), service)
    keyboard = build_inline_buttons(res.get("links", []))
    
    if res.get("token"):
        msg += f"\n\n🔑 `accountToken={escape_markdown(res.get('token'))}`"
    if res.get("error"):
        msg += f"\n\n⚠️ _{escape_markdown(res.get('error'))}_"
    
    await status_msg.edit_text(msg, parse_mode="MarkdownV2", reply_markup=keyboard)

# ---------------- Main ----------------
def main():
    print("🚀 Initializing bot...")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Public commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("services", services_handler))
    app.add_handler(CommandHandler("about", about_handler))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(verify_membership_callback, pattern="^verify_membership$"))
    
    # Admin commands
    app.add_handler(CommandHandler("stats", stats_handler))
    
    # Bypass commands
    app.add_handler(CommandHandler("bypass", bypass_handler))
    app.add_handler(CommandHandler("hubdrive", cmd_hubdrive))
    app.add_handler(CommandHandler("hubcloud", cmd_hubcloud))
    app.add_handler(CommandHandler("hubcdn", cmd_hubcdn))
    app.add_handler(CommandHandler("vcloud", cmd_vcloud))
    app.add_handler(CommandHandler("gdflix", cmd_gdflix))
    app.add_handler(CommandHandler("photolinx", cmd_photolinx))
    app.add_handler(CommandHandler("gofile", cmd_gofile))
    app.add_handler(CommandHandler("driveleech", cmd_driveleech))
    app.add_handler(CommandHandler("driveseed", cmd_driveseed))
    app.add_handler(CommandHandler("linkstore", cmd_linkstore))
    app.add_handler(CommandHandler("luxdrive", cmd_luxdrive))
    app.add_handler(CommandHandler("vifix", cmd_vifix))
    app.add_handler(CommandHandler("howblogs", cmd_howblogs))
    app.add_handler(CommandHandler("fastdl", cmd_fastdl))
    app.add_handler(CommandHandler("fastlinks", cmd_fastlinks))
    app.add_handler(CommandHandler("wlinkfast", cmd_wlinkfast))
    
    print("✅ Bot initialized successfully!")
    print(f"👤 Admin: {ADMIN_ID}")
    print(f"📢 Channel: {REQUIRED_CHANNEL}")
    print(f"🔗 Group: {GROUP_LINK}")
    print("🌐 Services: 20+ supported")
    print("⚡ Starting polling...")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
