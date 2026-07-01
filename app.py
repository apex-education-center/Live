from flask import Flask, render_template, request, Response, jsonify
import requests
import re
import urllib.parse
from bs4 import BeautifulSoup
import urllib3
from playwright.sync_api import sync_playwright
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__, template_folder='templates')

XTREAM_SERVER = "http://your-iptv-provider-domain.com:8080"
XTREAM_USERNAME = "your_username"
XTREAM_PASSWORD = "your_password"

otv_session = requests.Session()

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
    "alhadath": "https://live.alarabiya.net/alhadathpublish/alhadath.smil/playlist.m3u8",
    "alhadath_referer": "https://www.alhadath.net/",
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
    if not XTREAM_USERNAME or XTREAM_USERNAME == "your_username":
        return None
    return f"{XTREAM_SERVER}/live/{XTREAM_USERNAME}/{XTREAM_PASSWORD}/{stream_id}.m3u8"

stream_cache = {"url": None, "timestamp": 0}

def get_authenticated_stream():
    if stream_cache["url"] and (time.time() - stream_cache["timestamp"] < 3600):
        return stream_cache["url"]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            page = context.new_page()
            
            captured_url = None
            def handle_response(response):
                nonlocal captured_url
                if ".m3u8" in response.url and "edgenextcdn" not in response.url and ("bitmovin" in response.url or "pfs.gdn" in response.url or "broadcast" in response.url):
                    captured_url = response.url

            page.on("response", handle_response)
            page.goto("https://www.mtv.com.lb/live", timeout=15000)
            page.wait_for_timeout(3000) 
            browser.close()
            
            if captured_url:
                stream_cache["url"] = captured_url
                stream_cache["timestamp"] = time.time()
                return captured_url
    except Exception as e:
        print(f"[Scraper Error] {e}")
    return None

def extract_authenticated_otv_stream():
    return FALLBACKS["otv"]

def fetch_community_stream(channel_keyword, country_code="lb"):
    url = f"https://iptv-org.github.io/iptv/countries/{country_code}.m3u"
    try:
        response = requests.get(url, verify=False, timeout=3)
        if response.status_code == 200:
            lines = response.text.split('\n')
            for i, line in enumerate(lines):
                if channel_keyword.lower() in line.lower():
                    if "radio" in line.lower() and "radio" not in channel_keyword.lower():
                        continue
                    if i + 1 < len(lines):
                        stream_url = lines[i+1].strip()
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
    # Light-weight setup so the list populates in milliseconds
    channels = [
        {"id": "mtv", "name": "MTV Lebanon (TV)", "category": "Lebanon", "url": "DYNAMIC_MTV"},
        {"id": "lbci", "name": "LBCI Lebanon", "category": "Lebanon", "url": fetch_xtream_stream("67890") or FALLBACKS["lbci"]},
        {"id": "otv", "name": "OTV Lebanon", "category": "Lebanon", "url": fetch_xtream_stream("11223") or FALLBACKS["otv"]},
        {"id": "al_jadeed", "name": "Al Jadeed", "category": "Lebanon", "url": FALLBACKS["aljadeed"]},
        {"id": "nbn", "name": "NBN Lebanon", "category": "Lebanon", "url": FALLBACKS["nbn"]},
        {"id": "al_manar", "name": "Al Manar", "category": "Lebanon", "url": FALLBACKS["almanar"]},
        {"id": "teleliban", "name": "Tele Liban", "category": "Lebanon", "url": FALLBACKS["tele"]},
        {"id": "future_tv", "name": "Future TV", "category": "Lebanon", "url": FALLBACKS["future"]},
        {"id": "noursat", "name": "Noursat", "category": "Lebanon (Religious)", "url": FALLBACKS["noursat"]},
        {"id": "mariam_tv", "name": "Mariam TV", "category": "Lebanon (Cultural)", "url": FALLBACKS["mariam"]},
        {"id": "al_mayadeen", "name": "Al Mayadeen", "category": "News", "url": FALLBACKS["almayadeen"]},
        {"id": "alarabiya", "name": "Al Arabiya", "category": "News", "url": FALLBACKS["alarabiya"], "referer": FALLBACKS["alarabiya_referer"]},
        {"id": "alhadath", "name": "Al Hadath", "category": "News", "url": FALLBACKS["alhadath"], "referer": FALLBACKS["alhadath_referer"]},
        {"id": "aljazeera", "name": "Al Jazeera", "category": "News", "url": FALLBACKS["aljazeera"]},
        {"id": "cnbc", "name": "CNBC Arabiya", "category": "Business", "url": FALLBACKS["cnbc"]},
        {"id": "bloomberg", "name": "Bloomberg TV", "category": "Business", "url": FALLBACKS["bloomberg"]},
        {"id": "france24", "name": "France 24 (EN)", "category": "News", "url": FALLBACKS["france24"]},
        {"id": "abc_news", "name": "ABC News Live", "category": "News (US International)", "url": FALLBACKS["abcnews"]},
        {"id": "natgeo", "name": "Nat Geo Abu Dhabi", "category": "Documentary", "url": fetch_xtream_stream("44556") or FALLBACKS["natgeo"]}
    ]
    return jsonify(channels)

@app.route('/api/resolve_stream/<channel_id>')
def resolve_stream(channel_id):
    # Dynamically resolve heavy streams only when clicked
    if channel_id == "mtv":
        url = fetch_xtream_stream("12345") or get_authenticated_stream() or fetch_community_stream("mtv lebanon", "lb") or FALLBACKS["mtv"]
        return jsonify({"url": url})
    return jsonify({"error": "Standard stream"}), 400

@app.route('/proxy')
def stream_proxy():
    target_url = request.args.get('url')
    referer_header = request.args.get('referer')
    
    if not target_url or target_url.startswith("https://YOUR_IPTV_PROVIDER") or target_url == "DYNAMIC_MTV":
        return "Stream URL empty or unconfigured", 400

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
                if not stripped: continue
                if not stripped.startswith('#') and not stripped.startswith('http'):
                    if stripped.startswith('/'):
                        absolute_url = '/'.join(target_url.split('/')[:3]) + stripped
                    else:
                        absolute_url = base_url + '/' + stripped
                    param_url = f"/proxy?url={urllib.parse.quote_plus(absolute_url)}"
                    if referer_header: param_url += f"&referer={urllib.parse.quote_plus(referer_header)}"
                    rewritten_lines.append(param_url)
                elif stripped.startswith('http') and not stripped.startswith('/proxy'):
                    param_url = f"/proxy?url={urllib.parse.quote_plus(stripped)}"
                    if referer_header: param_url += f"&referer={urllib.parse.quote_plus(referer_header)}"
                    rewritten_lines.append(param_url)
                else:
                    rewritten_lines.append(line)

            return Response('\n'.join(rewritten_lines), status=req.status_code, headers=response_headers, content_type='application/vnd.apple.mpegurl')

        return Response(req.iter_content(chunk_size=32768), status=req.status_code, headers=response_headers, content_type=req.headers.get('Content-Type'))
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
