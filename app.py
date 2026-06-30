from flask import Flask, render_template, request, Response, jsonify
import requests
import re
import urllib.parse
from bs4 import BeautifulSoup
import urllib3
from playwright.sync_api import sync_playwright
import time

# Suppress SSL certificate warning logs in the console
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, template_folder='templates')

# =========================================================================
# AUTHORIZED XTREAM CODES CREDENTIALS
# If you have a paid or authorized IPTV subscription, insert your login
# details here. The backend will use standard API handshakes to fetch
# your dynamic, authorized stream tokens.
# =========================================================================
XTREAM_SERVER = "http://your-iptv-provider-domain.com:8080"
XTREAM_USERNAME = "your_username"
XTREAM_PASSWORD = "your_password"

# Persistent sessions
otv_session = requests.Session()

# 2026 Verified High-Availability Fallbacks for Lebanese & Public Channels
FALLBACKS = {
    "mtv": "https://hms.pfs.gdn/v1/broadcast/mtv/playlist.m3u8",
    "mtv_alt": "https://live.3cd.io/v1/broadcast/mtv/playlist.m3u8",
    "lbci": "https://mhd.itworkscdn.net/lbclive/lbc/playlist.m3u8",
    "otv": "https://otv.hibridcdn.net/otv/tv_abr/playlist.m3u8",
    "tele": "https://teleliban.b-cdn.net/live/stream/playlist.m3u8",
    "aljadeed": "http://185.9.2.18/chid_391/mono.m3u8",
    "nbn": "https://nbntv.me:8443/nbntv/index.m3u8",
    "almanar": "https://edge.fastpublish.me/live/index.m3u8",
    "natgeo": "https://YOUR_IPTV_PROVIDER.com/natgeo.m3u8",
    "alarabiya": "https://live.alarabiya.net/alarabiapublish/alarabiya.smil/playlist.m3u8",
    "alarabiya_referer": "https://www.alarabiya.net/",
    "aljazeera": "https://live-hls-apps-aja-v3-fa.getaj.net/AJA/index.m3u8",
    "cnbc": "https://cnbc-live.akamaized.net/cnbc/master.m3u8",
    "noursat": "https://cllive.itworkscdn.net/noursat/live.smil/playlist.m3u8",
    "mariam": "https://cllive.itworkscdn.net/mariamtv/live.smil/playlist.m3u8",
    "future": "https://futuretv.b-cdn.net/live/stream/playlist.m3u8",
    "almayadeen": "https://live.almayadeen.net/live/smil:almayadeen.smil/playlist.m3u8",
    "bloomberg": "https://bloomberg.com/media-manifest/streams/us.m3u8",
    "france24": "https://live.france24.com/hls/live/2037218-b/F24_EN_HI_HLS/master_5000.m3u8",
    "abcnews": "https://content.uplynk.com/channel/3324f2467c414329b3b0cc5cd987b6be.m3u8"
}

def fetch_xtream_stream(stream_id):
    """
    Standard protocol to fetch authenticated stream URLs from an Xtream Codes server.
    This resolves dynamic CDN tokens securely using authorized user credentials.
    """
    if not XTREAM_USERNAME or XTREAM_USERNAME == "your_username":
        return None
    return f"{XTREAM_SERVER}/live/{XTREAM_USERNAME}/{XTREAM_PASSWORD}/{stream_id}.m3u8"


# Simple cache to avoid re-logging in every time
stream_cache = {"url": None, "timestamp": 0}

def get_authenticated_stream():
    # Return from cache if less than 1 hour old
    if stream_cache["url"] and (time.time() - stream_cache["timestamp"] < 3600):
        return stream_cache["url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        page = context.new_page()
        
        captured_url = None
        def handle_response(response):
            nonlocal captured_url
            # Filter out blacklisted/expired CDNs completely
            if ".m3u8" in response.url and "edgenextcdn" not in response.url and ("bitmovin" in response.url or "pfs.gdn" in response.url or "broadcast" in response.url):
                captured_url = response.url

        page.on("response", handle_response)
        
        try:
            # Drop valid base cookies first
            page.goto("https://www.mtv.com.lb", timeout=30000)
            page.wait_for_timeout(2000)
            
            # Load streaming manifest
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
    """
    Automated headless bot to log into OTV's free system,
    extract the session token, and return the direct raw video stream.
    """
    payload = {
        'email': 'tvlivechannel9@gmail.com',
        'password': 'tvlivechannel12345'
    }
    
    if payload['email'] == 'tvlivechannel9@gmail.com':
        print("[OTV Scraper] Using public fallback. Insert valid credentials to enable automated login bypass.")
        return FALLBACKS["otv"]

    login_page_url = "https://otv.com.lb/login"
    live_page_url = "https://otv.com.lb/live"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # Get dynamic CSRF validation token
        get_login = otv_session.get(login_page_url, headers=headers, verify=False, timeout=5)
        soup = BeautifulSoup(get_login.text, 'html.parser')
        csrf_token = soup.find('input', {'name': '_token'})
        
        if csrf_token:
            payload['_token'] = csrf_token['value']

        # Execute backend login session handshake
        otv_session.post(login_page_url, data=payload, headers=headers, verify=False, timeout=5)
        
        # Scrape tokenized playback manifest
        live_page = otv_session.get(live_page_url, headers=headers, verify=False, timeout=5)
        match = re.search(r'(https://[^\s"\']+\.m3u8[^\s"\']*)', live_page.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"[OTV Scraper] Exception encountered: {e}")
    
    return FALLBACKS["otv"]

def fetch_community_stream(channel_keyword, country_code="lb"):
    """
    Automatically parses the global daily-maintained list for fresh streaming links.
    """
    url = f"https://iptv-org.github.io/iptv/countries/{country_code}.m3u"
    try:
        response = requests.get(url, verify=False, timeout=5)
        if response.status_code == 200:
            lines = response.text.split('\n')
            for i, line in enumerate(lines):
                if channel_keyword.lower() in line.lower():
                    # Bypass radio tags when querying a TV channel keyword context
                    if "radio" in line.lower() and "radio" not in channel_keyword.lower():
                        continue
                    
                    if i + 1 < len(lines):
                        stream_url = lines[i+1].strip()
                        
                        # Hard-blacklist the dead edgenextcdn link
                        if "edgenextcdn.net" in stream_url:
                            continue
                            
                        if stream_url.startswith("http"):
                            return stream_url
    except Exception:
        pass
    return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/channels')
def get_channels():
    """
    Compiles and delivers the final dynamic playlist.
    Uses Xtream Codes for protected premium streams, and scrapes community feeds for public ones.
    Categorized to create visual sections in the frontend interface.
    """
    channels = [
        {
            "id": "mtv",
            "name": "MTV Lebanon (TV)",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=100",
            "url": fetch_xtream_stream("12345") or get_authenticated_stream() or fetch_community_stream("mtv lebanon", "lb") or FALLBACKS["mtv"] or FALLBACKS["mtv_alt"]
        },
        {
            "id": "lbci",
            "name": "LBCI Lebanon",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=100",
            "url": fetch_xtream_stream("67890") or fetch_community_stream("lbci", "lb") or FALLBACKS["lbci"]
        },
        {
            "id": "otv",
            "name": "OTV Lebanon",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=100",
            "url": fetch_xtream_stream("11223") or extract_authenticated_otv_stream()
        },
        {
            "id": "al_jadeed",
            "name": "Al Jadeed",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=100",
            "url": fetch_community_stream("jadeed", "lb") or FALLBACKS["aljadeed"]
        },
        {
            "id": "nbn",
            "name": "NBN Lebanon",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=100",
            "url": fetch_community_stream("nbn", "lb") or FALLBACKS["nbn"]
        },
        {
            "id": "al_manar",
            "name": "Al Manar",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=100",
            "url": fetch_community_stream("manar", "lb") or FALLBACKS["almanar"]
        },
        {
            "id": "teleliban",
            "name": "Tele Liban",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=100",
            "url": fetch_community_stream("tele", "lb") or FALLBACKS["tele"]
        },
        {
            "id": "future_tv",
            "name": "Future TV",
            "category": "Lebanon",
            "logo": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=100",
            "url": fetch_community_stream("future", "lb") or FALLBACKS["future"]
        },
        {
            "id": "noursat",
            "name": "Noursat",
            "category": "Lebanon (Religious)",
            "logo": "https://images.unsplash.com/photo-1544427928-c49cddee01bb?w=100",
            "url": fetch_community_stream("noursat", "lb") or FALLBACKS["noursat"]
        },
        {
            "id": "mariam_tv",
            "name": "Mariam TV",
            "category": "Lebanon (Cultural)",
            "logo": "https://images.unsplash.com/photo-1517486808906-6ca8b3f04846?w=100",
            "url": fetch_community_stream("mariam", "lb") or FALLBACKS["mariam"]
        },
        {
            "id": "al_mayadeen",
            "name": "Al Mayadeen",
            "category": "News",
            "logo": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=100",
            "url": fetch_community_stream("mayadeen", "lb") or FALLBACKS["almayadeen"]
        },
        {
            "id": "alarabiya",
            "name": "Al Arabiya",
            "category": "News",
            "logo": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=100",
            "url": FALLBACKS["alarabiya"],
            "referer": FALLBACKS["alarabiya_referer"]
        },
        {
            "id": "aljazeera",
            "name": "Al Jazeera",
            "category": "News",
            "logo": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=100",
            "url": fetch_community_stream("jazeera", "qa") or FALLBACKS["aljazeera"]
        },
        {
            "id": "cnbc",
            "name": "CNBC Arabiya",
            "category": "Business",
            "logo": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=100",
            "url": fetch_community_stream("cnbc", "ae") or FALLBACKS["cnbc"]
        },
        {
            "id": "bloomberg",
            "name": "Bloomberg TV",
            "category": "Business",
            "logo": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=100",
            "url": fetch_community_stream("bloomberg", "us") or FALLBACKS["bloomberg"]
        },
        {
            "id": "france24",
            "name": "France 24 (EN)",
            "category": "News",
            "logo": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=100",
            "url": fetch_community_stream("france 24", "fr") or FALLBACKS["france24"]
        },
        {
            "id": "abc_news",
            "name": "ABC News Live",
            "category": "News (US International)",
            "logo": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=100",
            "url": fetch_community_stream("abc news", "us") or FALLBACKS["abcnews"]
        },
        {
            "id": "natgeo",
            "name": "Nat Geo Abu Dhabi",
            "category": "Documentary",
            "logo": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100",
            "url": fetch_xtream_stream("44556") or fetch_community_stream("geographic", "ae") or FALLBACKS["natgeo"]
        }
    ]
    return jsonify(channels)

@app.route('/proxy')
def stream_proxy():
    target_url = request.args.get('url')
    referer_header = request.args.get('referer')
    
    if not target_url or target_url.startswith("https://YOUR_IPTV_PROVIDER"):
        return "Stream URL not configured or dead", 400

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    if referer_header:
        headers['Referer'] = referer_header
    else:
        headers['Referer'] = '/'.join(target_url.split('/')[:3]) + '/'

    try:
        req = requests.get(target_url, headers=headers, stream=True, verify=False, timeout=10)
        
        exclude_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for name, value in req.headers.items() if name.lower() not in exclude_headers]
        response_headers.append(('Access-Control-Allow-Origin', '*'))

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
                    
                    param_url = f"/proxy?url={urllib.parse.quote_plus(absolute_url)}"
                    if referer_header:
                        param_url += f"&referer={urllib.parse.quote_plus(referer_header)}"
                    rewritten_lines.append(param_url)
                elif stripped.startswith('http') and not stripped.startswith('/proxy'):
                    param_url = f"/proxy?url={urllib.parse.quote_plus(stripped)}"
                    if referer_header:
                        param_url += f"&referer={urllib.parse.quote_plus(referer_header)}"
                    rewritten_lines.append(param_url)
                else:
                    rewritten_lines.append(line)

            rewritten_content = '\n'.join(rewritten_lines)
            return Response(rewritten_content, status=req.status_code, headers=response_headers, content_type='application/vnd.apple.mpegurl')

        def generate():
            for chunk in req.iter_content(chunk_size=32768):
                yield chunk

        return Response(generate(), status=req.status_code, headers=response_headers, content_type=req.headers.get('Content-Type'))
        
    except Exception as e:
        print(f"[Proxy Error] Failed to tunnel stream segment: {e}")
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)