from flask import Flask, render_template, request, Response, jsonify
import requests
import re
import urllib.parse
from bs4 import BeautifulSoup
import urllib3
from playwright.sync_api import sync_playwright
import time
import threading

# Suppress SSL certificate warning logs in the console
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, template_folder='templates')

# =========================================================================
# AUTHORIZED XTREAM CODES CREDENTIALS
# =========================================================================
XTREAM_SERVER = "http://your-iptv-provider-domain.com:8080"
XTREAM_USERNAME = "your_username"
XTREAM_PASSWORD = "your_password"

# Persistent sessions
otv_session = requests.Session()

# Verified Fallbacks (Locked to your working local streams)
FALLBACKS = {
    "mtv": "https://shd-gcp-live.edgenextcdn.net/live/bitmovin-mtv-lebanon/b8ebb2a5affb812f1541712adde10e26/index.m3u8",
    "mtv_alt": "https://live.3cd.io/v1/broadcast/mtv/playlist.m3u8",
    "otv": "https://otv.hibridcdn.net/otv/tv_abr/playlist.m3u8",
    "tele": "https://teleliban.b-cdn.net/live/stream/playlist.m3u8",
    "almanar": "https://edge.fastpublish.me/live/index.m3u8",
    "alarabiya": "https://live.alarabiya.net/alarabiapublish/alarabiya.smil/playlist.m3u8",
    "alarabiya_referer": "https://www.alarabiya.net/",
    "aljazeera_arabic": "https://live-hls-web-aja.getaj.net/AJA/index.m3u8",
    "cnbc": "https://cnbc-live.akamaized.net/cnbc/master.m3u8",
    "noursat": "https://cllive.itworkscdn.net/noursat/live.smil/playlist.m3u8",
    "future": "https://futuretv.b-cdn.net/live/stream/playlist.m3u8",
    "almayadeen": "https://live.almayadeen.net/live/smil:almayadeen.smil/playlist.m3u8",
    "bloomberg": "https://bloomberg.com/media-manifest/streams/us.m3u8",
    "france24": "https://live.france24.com/hls/live/2037218-b/F24_EN_HI_HLS/master_5000.m3u8"
}

def fetch_xtream_stream(stream_id):
    if not XTREAM_USERNAME or XTREAM_USERNAME == "your_username":
        return None
    return f"{XTREAM_SERVER}/live/{XTREAM_USERNAME}/{XTREAM_PASSWORD}/{stream_id}.m3u8"

stream_cache = {"url": None, "timestamp": 0}

def get_authenticated_stream():
    if stream_cache["url"] and (time.time() - stream_cache["timestamp"] < 3600):
        return stream_cache["url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        page = context.new_page()

        captured_url = None
        def handle_response(response):
            nonlocal captured_url
            if ".m3u8" in response.url and ("bitmovin" in response.url or "pfs.gdn" in response.url or "broadcast" in response.url or "edgenextcdn" in response.url):
                captured_url = response.url

        page.on("response", handle_response)

        try:
            page.goto("https://www.mtv.com.lb", timeout=30000)
            page.wait_for_timeout(2000)
            page.goto("https://www.mtv.com.lb/live", timeout=60000)
            page.wait_for_timeout(7000)
        except Exception as e:
            print(f"Playwright error: {e}")
        finally:
            browser.close()

        if captured_url:
            stream_cache["url"] = captured_url
            stream_cache["timestamp"] = time.time()
        return captured_url

def extract_authenticated_otv_stream():
    payload = {
        'email': 'tvlivechannel9@gmail.com',
        'password': 'tvlivechannel12345'
    }

    if payload['email'] == 'tvlivechannel9@gmail.com':
        return FALLBACKS["otv"]

    login_page_url = "https://otv.com.lb/login"
    live_page_url = "https://otv.com.lb/live"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        get_login = otv_session.get(login_page_url, headers=headers, verify=False, timeout=5)
        soup = BeautifulSoup(get_login.text, 'html.parser')
        csrf_token = soup.find('input', {'name': '_token'})

        if csrf_token:
            payload['_token'] = csrf_token['value']

        otv_session.post(login_page_url, data=payload, headers=headers, verify=False, timeout=5)
        live_page = otv_session.get(live_page_url, headers=headers, verify=False, timeout=5)
        match = re.search(r'(https://[^\s"\']+\.m3u8[^\s"\']*)', live_page.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"[OTV Scraper] Exception encountered: {e}")

    return FALLBACKS["otv"]

def fetch_community_stream(channel_keyword, country_code="lb"):
    url = f"https://iptv-org.github.io/iptv/countries/{country_code}.m3u"
    try:
        response = requests.get(url, verify=False, timeout=5)
        if response.status_code == 200:
            lines = response.text.split('\n')
            for i, line in enumerate(lines):
                if channel_keyword.lower() in line.lower():
                    if "radio" in line.lower() and "radio" not in channel_keyword.lower():
                        continue

                    if i + 1 < len(lines):
                        stream_url = lines[i+1].strip()
                        if stream_url.startswith("http"):
                            return stream_url
    except Exception:
        pass
    return None

def build_channel_list():
    channels = [
        {
            "id": "mtv",
            "name": "MTV Lebanon",
            "category": "Lebanon",
            "url": fetch_xtream_stream("12345") or FALLBACKS["mtv"] or get_authenticated_stream() or FALLBACKS["mtv_alt"]
        },
        {
            "id": "otv",
            "name": "OTV Lebanon",
            "category": "Lebanon",
            "url": fetch_xtream_stream("11223") or extract_authenticated_otv_stream()
        },
        {
            "id": "al_manar",
            "name": "Al Manar",
            "category": "Lebanon",
            "url": fetch_community_stream("manar", "lb") or FALLBACKS["almanar"]
        },
        {
            "id": "teleliban",
            "name": "Tele Liban",
            "category": "Lebanon",
            "url": FALLBACKS["tele"] or fetch_community_stream("tele liban", "lb")
        },
        {
            "id": "future_tv",
            "name": "Future TV",
            "category": "Lebanon",
            "url": fetch_community_stream("future", "lb") or FALLBACKS["future"]
        },
        {
            "id": "noursat",
            "name": "Noursat",
            "category": "Lebanon (Religious)",
            "url": fetch_community_stream("noursat", "lb") or FALLBACKS["noursat"]
        },
        {
            "id": "al_mayadeen",
            "name": "Al Mayadeen",
            "category": "News",
            "url": fetch_community_stream("mayadeen", "lb") or FALLBACKS["almayadeen"]
        },
        {
            "id": "alarabiya",
            "name": "Al Arabiya",
            "category": "News",
            "url": FALLBACKS["alarabiya"],
            "referer": FALLBACKS["alarabiya_referer"]
        },
        {
            "id": "aljazeera_arabic",
            "name": "Al Jazeera Arabic",
            "category": "News",
            "url": FALLBACKS["aljazeera_arabic"]
        },
        {
            "id": "cnbc",
            "name": "CNBC Arabiya",
            "category": "Business",
            "url": fetch_community_stream("cnbc", "ae") or FALLBACKS["cnbc"]
        },
        {
            "id": "bloomberg",
            "name": "Bloomberg TV",
            "category": "Business",
            "url": fetch_community_stream("bloomberg", "us") or FALLBACKS["bloomberg"]
        },
        {
            "id": "france24",
            "name": "France 24 (EN)",
            "category": "News",
            "url": fetch_community_stream("france 24", "fr") or FALLBACKS["france24"]
        }
    ]
    return channels

channel_cache = {
    "channels": [],
    "last_updated": 0,
    "building": False
}

REFRESH_INTERVAL_SECONDS = 30 * 60

def build_fallback_only_list():
    return [
        {"id": "mtv", "name": "MTV Lebanon", "category": "Lebanon", "url": FALLBACKS["mtv"]},
        {"id": "otv", "name": "OTV Lebanon", "category": "Lebanon", "url": FALLBACKS["otv"]},
        {"id": "al_manar", "name": "Al Manar", "category": "Lebanon", "url": FALLBACKS["almanar"]},
        {"id": "teleliban", "name": "Tele Liban", "category": "Lebanon", "url": FALLBACKS["tele"]},
        {"id": "future_tv", "name": "Future TV", "category": "Lebanon", "url": FALLBACKS["future"]},
        {"id": "noursat", "name": "Noursat", "category": "Lebanon (Religious)", "url": FALLBACKS["noursat"]},
        {"id": "al_mayadeen", "name": "Al Mayadeen", "category": "News", "url": FALLBACKS["almayadeen"]},
        {"id": "alarabiya", "name": "Al Arabiya", "category": "News", "url": FALLBACKS["alarabiya"], "referer": FALLBACKS["alarabiya_referer"]},
        {"id": "aljazeera_arabic", "name": "Al Jazeera Arabic", "category": "News", "url": FALLBACKS["aljazeera_arabic"]},
        {"id": "cnbc", "name": "CNBC Arabiya", "category": "Business", "url": FALLBACKS["cnbc"]},
        {"id": "bloomberg", "name": "Bloomberg TV", "category": "Business", "url": FALLBACKS["bloomberg"]},
        {"id": "france24", "name": "France 24 (EN)", "category": "News", "url": FALLBACKS["france24"]},
    ]

def refresh_channel_cache():
    if channel_cache["building"]:
        return
    channel_cache["building"] = True
    try:
        fresh = build_channel_list()
        channel_cache["channels"] = fresh
        channel_cache["last_updated"] = time.time()
        print(f"[Cache] Channel list refreshed with {len(fresh)} channels.")
    except Exception as e:
        print(f"[Cache] Failed to refresh channel list: {e}")
    finally:
        channel_cache["building"] = False

def background_refresh_loop():
    channel_cache["channels"] = build_fallback_only_list()
    channel_cache["last_updated"] = time.time()
    refresh_channel_cache()
    while True:
        time.sleep(REFRESH_INTERVAL_SECONDS)
        refresh_channel_cache()

_refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
_refresh_thread.start()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/channels')
def get_channels():
    return jsonify(channel_cache["channels"])

@app.route('/api/channels/refresh', methods=['POST'])
def force_refresh():
    if channel_cache["building"]:
        return jsonify({"status": "already_building"}), 202
    threading.Thread(target=refresh_channel_cache, daemon=True).start()
    return jsonify({"status": "refresh_started"}), 202

@app.route('/proxy')
def stream_proxy():
    target_url = request.args.get('url')
    
    # 1. Basic Validation
    if not target_url or target_url.startswith("https://YOUR_IPTV_PROVIDER"):
        return "Stream URL not configured or dead", 400

    # 2. Determine Referer
    # Use the passed referer or default to the domain of the target URL
    referer_header = request.args.get('referer')
    if not referer_header:
        if "mtv" in target_url:
            referer_header = "https://www.mtv.com.lb/"
        else:
            referer_header = '/'.join(target_url.split('/')[:3]) + '/'

    # 3. Define Headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': referer_header,
        'Origin': '/'.join(referer_header.split('/')[:3])
    }

    try:
        # 4. Perform the Request
        req = requests.get(target_url, headers=headers, stream=True, verify=False, timeout=10)
        
        exclude_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for name, value in req.headers.items() if name.lower() not in exclude_headers]
        response_headers.append(('Access-Control-Allow-Origin', '*'))

        # 5. Handle M3U8 Playlist Rewriting
        if '.m3u8' in target_url or 'playlist' in target_url:
            content = req.text
            base_url = target_url.rsplit('/', 1)[0]
            lines = content.split('\n')
            rewritten_lines = []

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                if not stripped.startswith('#') and not stripped.startswith('http'):
                    if stripped.startswith('/'):
                        domain_root = '/'.join(target_url.split('/')[:3])
                        absolute_url = domain_root + stripped
                    else:
                        absolute_url = base_url + '/' + stripped

                    param_url = f"/proxy?url={urllib.parse.quote_plus(absolute_url)}&referer={urllib.parse.quote_plus(referer_header)}"
                    rewritten_lines.append(param_url)
                elif stripped.startswith('http') and not stripped.startswith('/proxy'):
                    param_url = f"/proxy?url={urllib.parse.quote_plus(stripped)}&referer={urllib.parse.quote_plus(referer_header)}"
                    rewritten_lines.append(param_url)
                else:
                    rewritten_lines.append(line)

            rewritten_content = '\n'.join(rewritten_lines)
            return Response(rewritten_content, status=req.status_code, headers=response_headers, content_type='application/vnd.apple.mpegurl')

        # 6. Handle Video Segments (TS files)
        def generate():
            for chunk in req.iter_content(chunk_size=32768):
                yield chunk

        return Response(generate(), status=req.status_code, headers=response_headers, content_type=req.headers.get('Content-Type'))

    except Exception as e:
        print(f"[Proxy Error] Failed to tunnel stream segment: {e}")
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
