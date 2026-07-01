# Channels Plus

Channels Plus is a custom IPTV channel viewer. It has a Flask backend and a single page player on the frontend. Channels are grouped by category, searchable, and streamed through a server side proxy, with a separate flow for channels that only offer an official web player instead of a direct stream: https://live-c489.onrender.com


## What it does

The main screen shows a live channel grid, grouped into categories you can collapse or expand, and each channel gets its own logo (if a logo is missing or fails to load, it falls back to showing the channel's initials). There's a search box that filters instantly across channel name and category.

Streams play through hls.js for broad browser support. They're routed through a backend proxy at /proxy so that restrictive Referer headers don't block playback.

Some channels don't offer a proxyable stream at all, only an official site with its own player. Those are tagged as external and instead of trying to embed something that won't work, the app shows a card with an "Open official stream" button that links straight out to the source.

The layout is responsive. On desktop there's a fixed sidebar; on tablet and mobile it becomes a slide in drawer, with spacing that accounts for notches and safe areas on phones. The player also shows its connection state as it changes: connecting, live, error, or external link.

## Tech stack

The backend is Flask (Python). The frontend is a single page of HTML, CSS and JS with no build step, using hls.js for HLS playback. It's containerized with Docker and deployed on Render.

## Project structure

The general shape of the app looks like this, though you should adjust it to match your actual repo:

app.py is the Flask app that serves the frontend and handles /api/channels and /proxy. channels.json holds the channel list returned by /api/channels. There's a static folder for assets and a templates folder (or wherever index.html actually lives), plus a Dockerfile and this README.

## Channel data format

/api/channels should return a JSON array of channel objects. Each one needs an id (a unique string used to target the right element in the DOM), a name to display, and a category used for grouping in the sidebar. It also needs a url, which is either the HLS stream address or, for external channels, the official site's URL.

A few fields are optional. logo is an image URL shown in a white tile next to the channel name. referer gets passed along to /proxy to satisfy a stream's Referer check if it has one. external is a boolean that, when true, makes the channel skip the proxy and player entirely and show the "Open official stream" link instead. You don't actually need to set that flag per channel if the whole category is meant to be external: any category containing the word "External" (case insensitive) is treated the same way automatically.

Here's an example of two entries, one normal and one external:

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

GET /api/channels returns the channel list described above. GET /proxy takes a url query parameter (and an optional referer parameter) and proxies and rewrites the HLS manifest and segments so the player can load streams that would otherwise reject cross origin or missing referer requests.

## Running it locally

Clone the repo, move into the project folder, install dependencies with pip install -r requirements.txt, then run python app.py. The app should then be available at http://localhost:5000, or whichever port app.py binds to.

## Running it with Docker

Build the image with docker build -t channels-plus . and run it with docker run -p 5000:5000 channels-plus.

## Deployment

This project is set up to deploy on Render using the included Dockerfile. Push to your connected branch and Render builds and deploys it automatically.

## A note on legal use

This player is meant to work with channel sources you actually have the rights or authorization to redistribute. Proxying and rebroadcasting live broadcast content without permission from the rights holder isn't something this project is meant to support. For any channel you don't control or hold rights to, use the external flow instead, so viewers get pointed to the official source rather than a proxied copy.
