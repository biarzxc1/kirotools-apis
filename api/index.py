import requests
import json
import urllib3
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kirotools API",
    description="UID live checker API by Kirotools",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ───────────────────────────────────────────────────────────────────
HITOOLS_URL    = "https://hitools.pro/api/check-live-uid"
DEFAULT_CSRF   = "6de6f24f8447da972f7094f0a7e8f6735d30204bb67e387ade6985f96365921b%7C18f833da24715fa9ee0801d39ff08bc732de64548ebed402ff7d54ab0ab8622b"
DEFAULT_CB_URL = "https%3A%2F%2Fhitools.pro"

UPSTREAM_HEADERS = {
    "sec-ch-ua-platform": "Windows",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    "content-type": "application/json",
    "sec-ch-ua-mobile": "?0",
    "accept": "*/*",
    "sec-gpc": "1",
    "accept-language": "en-US,en;q=0.5",
    "origin": "https://hitools.pro",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://hitools.pro/check-live-uid",
    "priority": "u=1, i",
}

# ── Models ───────────────────────────────────────────────────────────────────
class CheckUIDRequest(BaseModel):
    uids: List[str]

# ── Helper ───────────────────────────────────────────────────────────────────
def fetch_from_hitools(uids: List[str], csrf: str, cb_url: str) -> List[dict]:
    cookies = {
        "__Host-next-auth.csrf-token": csrf,
        "__Secure-next-auth.callback-url": cb_url,
    }
    resp = requests.post(
        HITOOLS_URL,
        headers=UPSTREAM_HEADERS,
        cookies=cookies,
        json={"uids": uids},
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()

    results = []
    for line in resp.text.strip().splitlines():
        line = line.strip()
        if line:
            results.append(json.loads(line))
    return results

# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "api": "Kirotools API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/check-live-uid": "Check if Facebook UIDs are live",
            "GET  /api/health":         "Health check",
            "GET  /docs":               "Swagger UI",
        }
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "kirotools-api"}

@app.post("/api/check-live-uid")
def check_live_uid(
    body: CheckUIDRequest,
    x_csrf_token:   Optional[str] = Header(default=None, alias="X-CSRF-Token"),
    x_callback_url: Optional[str] = Header(default=None, alias="X-Callback-URL"),
):
    """
    Check whether Facebook UIDs are live or dead.

    - **uids**: list of UID strings to check
    - **X-CSRF-Token** *(optional)*: override default CSRF token
    - **X-Callback-URL** *(optional)*: override default callback URL
    """
    if not body.uids:
        raise HTTPException(status_code=400, detail="uids list cannot be empty")

    csrf   = x_csrf_token   or DEFAULT_CSRF
    cb_url = x_callback_url or DEFAULT_CB_URL

    try:
        results = fetch_from_hitools(body.uids, csrf, cb_url)
        return JSONResponse(content=results)

    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstream request failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse upstream response: {str(e)}")

# ── Vercel Serverless Handler ─────────────────────────────────────────────────
from mangum import Mangum
handler = Mangum(app, lifespan="off")
