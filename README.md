# Calgary Water Quality & pH Monitoring

Real-time water quality monitoring web application ingesting City of Calgary Open Data SODA API records (`y8as-bmzj` and `kc8x-fu3f`).

Deployed on `water.snkaa.ca` (Port 8521) via Cloudflare Tunnel.

## Features
- Ingestion of discrete watershed samples and continuous sonde telemetry.
- Current pH monitoring vs. Hot Tub optimal target (7.50).
- Interactive chemical dosing calculator for sodium bisulfate / pH decreaser.
- Automated periodic background synchronization.

## Running Locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
