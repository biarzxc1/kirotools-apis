import requests
import json
import urllib3
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from typing import List, Optional
from mangum import Mangum

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kirotools API",
    description="""
## 🔧 Kirotools API

A powerful Facebook UID utility API.

### Features
- ✅ Check if Facebook UIDs are **live or dead**
- 🔍 Find a **Facebook ID** from a profile URL or username
- ⚡ Supports both **GET** (query params) and **POST** (JSON body)

### Authentication
No API key required. Just call the endpoints directly.

### Notes
- All responses are in **JSON**
- Multiple UIDs can be checked in a single request
- Rate limiting may apply for large batches
""",
    version="1.0.0",
    contact={
        "name": "Kirotools",
        "url": "https://github.com/biaruuu",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {
            "name": "UID Checker",
            "description": "Check whether Facebook UIDs are live or dead.",
        },
        {
            "name": "Facebook Lookup",
            "description": "Find Facebook IDs from profile URLs or usernames.",
        },
        {
            "name": "System",
            "description": "Health check and API info.",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ───────────────────────────────────────────────────────────────────
HITOOLS_URL         = "https://hitools.pro/api/check-live-uid"
HITOOLS_FINDID_URL  = "https://hitools.pro/api/find-facebook-id"
DEFAULT_CSRF        = "6de6f24f8447da972f7094f0a7e8f6735d30204bb67e387ade6985f96365921b%7C18f833da24715fa9ee0801d39ff08bc732de64548ebed402ff7d54ab0ab8622b"
DEFAULT_CB_URL      = "https%3A%2F%2Fhitools.pro"

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
    "referer": "https://hitools.pro/find-facebook-id",
    "priority": "u=1, i",
}

def get_cookies():
    return {
        "__Host-next-auth.csrf-token": DEFAULT_CSRF,
        "__Secure-next-auth.callback-url": DEFAULT_CB_URL,
    }

# ── Models ───────────────────────────────────────────────────────────────────
class CheckUIDRequest(BaseModel):
    uids: List[str] = Field(
        ...,
        description="List of Facebook UIDs to check",
        examples=[["100078365118623", "987654321"]],
        min_length=1,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Single UID",
                    "value": {"uids": ["100078365118623"]},
                },
                {
                    "summary": "Multiple UIDs",
                    "value": {"uids": ["100078365118623", "987654321", "111222333"]},
                },
            ]
        }
    }

class FindFacebookIDRequest(BaseModel):
    url: str = Field(
        ...,
        description="Facebook profile URL or username to look up",
        examples=["https://www.facebook.com/zuck"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Profile URL",
                    "value": {"url": "https://www.facebook.com/zuck"},
                },
                {
                    "summary": "Custom URL",
                    "value": {"url": "https://www.facebook.com/some.username"},
                },
            ]
        }
    }

class UIDResult(BaseModel):
    uid: str = Field(..., description="The Facebook UID that was checked")
    live: bool = Field(..., description="True if the account is live, False if dead/deactivated")

class FindIDResult(BaseModel):
    success: bool = Field(..., description="Whether the lookup was successful")
    id: Optional[str] = Field(None, description="The Facebook numeric ID found")
    type: Optional[str] = Field(None, description="Account type (e.g. profile, page)")

# ── Helpers ──────────────────────────────────────────────────────────────────
def fetch_check_uids(uids: List[str]) -> List[dict]:
    resp = requests.post(
        HITOOLS_URL,
        headers=UPSTREAM_HEADERS,
        cookies=get_cookies(),
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

def fetch_find_facebook_id(url: str) -> dict:
    resp = requests.post(
        HITOOLS_FINDID_URL,
        headers=UPSTREAM_HEADERS,
        cookies=get_cookies(),
        json={"url": url},
        timeout=25,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()

def handle_upstream_errors(e: Exception):
    if isinstance(e, requests.exceptions.HTTPError):
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {str(e)}")
    elif isinstance(e, requests.exceptions.RequestException):
        raise HTTPException(status_code=503, detail=f"Upstream request failed: {str(e)}")
    elif isinstance(e, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail=f"Failed to parse upstream response: {str(e)}")
    raise HTTPException(status_code=500, detail=str(e))

# ── System Routes ─────────────────────────────────────────────────────────────
@app.get(
    "/",
    tags=["System"],
    summary="API Info",
    response_description="Returns API name, version, and available endpoints",
)
def root():
    """Returns basic info about the Kirotools API."""
    return {
        "api": "Kirotools API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "GET  /api/checkliveuid?uid=UID":  "Check UID(s) via query param",
            "POST /api/check-live-uid":        "Check UID(s) via JSON body",
            "GET  /api/findfbid?url=URL":      "Find Facebook ID via query param",
            "POST /api/find-facebook-id":      "Find Facebook ID via JSON body",
            "GET  /api/health":                "Health check",
        },
    }

@app.get(
    "/api/health",
    tags=["System"],
    summary="Health Check",
    response_description="Returns service status",
)
def health():
    """Check if the API is running correctly."""
    return {"status": "ok", "service": "kirotools-api"}


# ── UID Checker Routes ────────────────────────────────────────────────────────
@app.get(
    "/api/checkliveuid",
    tags=["UID Checker"],
    summary="Check Live UIDs (Query Params)",
    response_description="List of UIDs with their live status",
    responses={
        200: {
            "description": "Successfully checked UIDs",
            "content": {
                "application/json": {
                    "examples": {
                        "single": {
                            "summary": "Single UID result",
                            "value": [{"uid": "100078365118623", "live": True}],
                        },
                        "multiple": {
                            "summary": "Multiple UID results",
                            "value": [
                                {"uid": "100078365118623", "live": True},
                                {"uid": "987654321", "live": False},
                            ],
                        },
                    }
                }
            },
        },
        400: {"description": "No UIDs provided"},
        502: {"description": "Upstream API error"},
        503: {"description": "Upstream service unavailable"},
    },
)
def check_live_uid_get(
    uid: List[str] = Query(
        ...,
        description="One or more Facebook UIDs to check. Repeat param for multiple.",
        examples=["100078365118623"],
    ),
):
    """
    Check if Facebook UID(s) are **live** or **dead** using query parameters.

    **Single UID:**
    ```
    GET /api/checkliveuid?uid=100078365118623
    ```

    **Multiple UIDs:**
    ```
    GET /api/checkliveuid?uid=100078365118623&uid=987654321
    ```
    """
    if not uid:
        raise HTTPException(status_code=400, detail="At least one uid param is required")
    try:
        return JSONResponse(content=fetch_check_uids(uid))
    except Exception as e:
        handle_upstream_errors(e)


@app.post(
    "/api/check-live-uid",
    tags=["UID Checker"],
    summary="Check Live UIDs (JSON Body)",
    response_description="List of UIDs with their live status",
    responses={
        200: {
            "description": "Successfully checked UIDs",
            "content": {
                "application/json": {
                    "examples": {
                        "live": {
                            "summary": "Live account",
                            "value": [{"uid": "100078365118623", "live": True}],
                        },
                        "dead": {
                            "summary": "Dead/deactivated account",
                            "value": [{"uid": "987654321", "live": False}],
                        },
                    }
                }
            },
        },
        400: {"description": "Empty uids list"},
        502: {"description": "Upstream API error"},
        503: {"description": "Upstream service unavailable"},
    },
)
def check_live_uid_post(body: CheckUIDRequest):
    """
    Check if Facebook UID(s) are **live** or **dead** using a JSON body.

    Pass one or more UIDs in the `uids` array:
    ```json
    { "uids": ["100078365118623", "987654321"] }
    ```
    """
    if not body.uids:
        raise HTTPException(status_code=400, detail="uids list cannot be empty")
    try:
        return JSONResponse(content=fetch_check_uids(body.uids))
    except Exception as e:
        handle_upstream_errors(e)


# ── Find Facebook ID Routes ───────────────────────────────────────────────────
@app.get(
    "/api/findfbid",
    tags=["Facebook Lookup"],
    summary="Find Facebook ID (Query Param)",
    response_description="Facebook numeric ID and account type",
    responses={
        200: {
            "description": "Facebook ID found successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "profile": {
                            "summary": "Profile result",
                            "value": {"success": True, "id": "100078365118623", "type": "profile"},
                        },
                        "page": {
                            "summary": "Page result",
                            "value": {"success": True, "id": "112233445566", "type": "page"},
                        },
                        "not_found": {
                            "summary": "Not found",
                            "value": {"success": False, "id": None, "type": None},
                        },
                    }
                }
            },
        },
        400: {"description": "Missing url param"},
        502: {"description": "Upstream API error"},
        503: {"description": "Upstream service unavailable"},
    },
)
def find_facebook_id_get(
    url: str = Query(
        ...,
        description="Facebook profile URL to look up",
        examples=["https://www.facebook.com/zuck"],
    ),
):
    """
    Find the numeric Facebook ID from a **profile URL** using a query param.

    ```
    GET /api/findfbid?url=https://www.facebook.com/zuck
    ```
    """
    if not url:
        raise HTTPException(status_code=400, detail="url param is required")
    try:
        return JSONResponse(content=fetch_find_facebook_id(url))
    except Exception as e:
        handle_upstream_errors(e)


@app.post(
    "/api/find-facebook-id",
    tags=["Facebook Lookup"],
    summary="Find Facebook ID (JSON Body)",
    response_description="Facebook numeric ID and account type",
    responses={
        200: {
            "description": "Facebook ID found successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "profile": {
                            "summary": "Profile result",
                            "value": {"success": True, "id": "100078365118623", "type": "profile"},
                        },
                        "page": {
                            "summary": "Page result",
                            "value": {"success": True, "id": "112233445566", "type": "page"},
                        },
                    }
                }
            },
        },
        400: {"description": "Missing url field"},
        502: {"description": "Upstream API error"},
        503: {"description": "Upstream service unavailable"},
    },
)
def find_facebook_id_post(body: FindFacebookIDRequest):
    """
    Find the numeric Facebook ID from a **profile URL** using a JSON body.

    ```json
    { "url": "https://www.facebook.com/zuck" }
    ```

    Returns the numeric ID and account type (profile or page).
    """
    if not body.url:
        raise HTTPException(status_code=400, detail="url field is required")
    try:
        return JSONResponse(content=fetch_find_facebook_id(body.url))
    except Exception as e:
        handle_upstream_errors(e)


# ── Vercel Serverless Handler ─────────────────────────────────────────────────
handler = Mangum(app, lifespan="off")
