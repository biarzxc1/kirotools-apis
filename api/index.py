import requests
import json
import urllib3
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from mangum import Mangum

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kirotools API",
    description="UID live checker API by Kirotools",
    version="1.0.0",
    root_path="",
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
        timeout=25,
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
            "GET  /api/checkliveuid?uid=UID":           "Check single UID (query param)",
            "GET  /api/checkliveuid?uid=UID1&uid=UID2": "Check multiple UIDs (query param)",
            "POST /api/check-live-uid":                 "Check UIDs (JSON body)",
            "GET  /api/health":                         "Health check",
            "GET  /docs":                               "Swagger UI",
        }
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "kirotools-api"}


# ── GET  /api/checkliveuid?uid=123&uid=456 ───────────────────────────────────
@app.get("/api/checkliveuid")
def check_live_uid_get(
    uid: List[str] = Query(..., description="One or more Facebook UIDs to check"),
):
    """
    Check UIDs via query params.

    **Examples:**
    - Single:   `/api/checkliveuid?uid=100078365118623`
    - Multiple: `/api/checkliveuid?uid=100078365118623&uid=987654321`
    """
    if not uid:
        raise HTTPException(status_code=400, detail="At least one uid param is required")

    try:
        results = fetch_from_hitools(uid, DEFAULT_CSRF, DEFAULT_CB_URL)
        return JSONResponse(content=results)

    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Upstream request failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse upstream response: {str(e)}")


# ── POST /api/check-live-uid (JSON body, kept for compatibility) ──────────────
@app.post("/api/check-live-uid")
def check_live_uid_post(
    body: CheckUIDRequest,
    x_csrf_token:   Optional[str] = Header(default=None, alias="X-CSRF-Token"),
    x_callback_url: Optional[str] = Header(default=None, alias="X-Callback-URL"),
):
    """
    Check UIDs via JSON body.

    ```json
    { "uids": ["100078365118623", "987654321"] }
    ```
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
handler = Mangum(app, lifespan="off")
