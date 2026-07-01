# Channels Plus

A custom IPTV channel viewer with a Flask backend and a single-page player frontend. Channels are grouped by category, searchable, and streamed through a server-side proxy — with a dedicated flow for channels that only offer an official web player instead of a direct stream:
https://live-c489.onrender.com


## Features

- **Live channel grid** — channels grouped into collapsible categories, each with its own logo (falls back to initials if a logo is missing or fails to load).
- **Search** — instant filter across channel name and category.
- **HLS playback** — streams are loaded through `hls.js` for broad browser support, routed through a backend proxy (`/proxy`) so restrictive `Referer` headers don't block playback.
- **External-link channels** — channels tagged as external (e.g. official broadcaster sites like MTV Lebanon or Tele Liban) skip the proxy entirely and show an "Open official stream" card that links out to the source, instead of trying to embed a stream that isn't proxyable.
- **Responsive UI** — full desktop layout with a fixed sidebar; on tablet/mobile the sidebar becomes a slide-in drawer, with safe-area-aware spacing for notched phones.
- **Status states** — the player shows live connection status (connecting / live / error / external link) at a glance.

## Tech stack

- **Backend:** Flask (Python)
- **Frontend:** Single-page HTML/CSS/JS, no build step, `hls.js` for HLS playback
- **Deployment:** Docker, deployed on Render

## Project structure

```
.
├── app.py              # Flask app: serves the frontend, /api/channels, /proxy
├── channels.json        # Channel list consumed by /api/channels
├── static/               # (if applicable) static assets
├── templates/            # or wherever index.html is served from
├── Dockerfile
└── README.md
```

> Adjust the tree above to match your actual repo layout — this reflects the general shape of the app based on the endpoints the frontend calls.

## Channel data format

`/api/channels` should return a JSON array. Each channel object supports:

| Field      | Type    | Required | Description |
|------------|---------|----------|-------------|
| `id`       | string  | yes | Unique identifier, used for DOM targeting |
| `name`     | string  | yes | Display name |
| `category` | string  | yes | Used to group channels in the sidebar |
| `url`      | string  | yes | Stream URL (HLS `.m3u8`) — or the official site URL for external channels |
| `logo`     | string  | no  | Logo image URL, shown in a white tile |
| `referer`  | string  | no  | Sent to `/proxy` to satisfy stream `Referer` checks |
| `external` | boolean | no  | If `true`, the channel bypasses the proxy/player and shows an "Open official stream" link instead |

A channel is also treated as external if its `category` contains the word "External" (case-insensitive), so no `external` flag is required for a whole category of link-outs.

Example:

```json
[
  {
    "id": "lbc",
    "name": "LBC",
    "category": "Lebanon",
    "url": "https://example.com/lbc/stream.m3u8",
    "logo": "https://example.com/logos/lbc.png"
  },
  {
    "id": "mtv-official",
    "name": "MTV Lebanon (Watch Official)",
    "category": "External Links",
    "url": "https://mtv.com.lb/live",
    "logo": "https://example.com/logos/mtv.png"
  }
]
```

## API endpoints

- `GET /api/channels` — returns the channel list described above.
- `GET /proxy?url=<stream_url>&referer=<referer>` — proxies and rewrites the HLS manifest/segments so the player can load streams that would otherwise reject cross-origin or missing-referer requests.

## Running locally

```bash
# clone and enter the project
git clone <your-repo-url>
cd channels-plus

# install dependencies
pip install -r requirements.txt

# run the app
python app.py
```

The app should then be available at `http://localhost:5000` (or whichever port `app.py` binds to).

## Running with Docker

```bash
docker build -t channels-plus .
docker run -p 5000:5000 channels-plus
```

## Deployment

This project is set up to deploy on [Render](https://render.com) using the included `Dockerfile`. Push to your connected branch and Render will build and deploy automatically.

## Notes on legal use

This player is built to work with channel sources you have the rights or authorization to redistribute. Proxying and rebroadcasting live broadcast content without authorization from the rights holder is not supported or endorsed — use the `external` link-out flow for any channel where you don't control or have rights to the stream itself, and it will simply point viewers to the official source instead.
