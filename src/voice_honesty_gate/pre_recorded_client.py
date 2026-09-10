"""Live client for AssemblyAI's pre-recorded transcription REST API.

Endpoints, auth, and response shapes are quoted and cited in full in
docs/API_NOTES.md ("Pre-recorded transcription API" section, fetched from
assemblyai.com/docs on 2026-09-09); this module does not invent anything
not sourced there.

  1. POST https://api.assemblyai.com/v2/upload            (raw bytes)  -> {"upload_url": "..."}
  2. POST https://api.assemblyai.com/v2/transcript         (JSON)      -> {"id": "...", "status": "queued", ...}
  3. GET  https://api.assemblyai.com/v2/transcript/{id}                -> {"status": "...", "text": "...", ...}

Auth header on every call: "authorization: <api key>" (no "Bearer" prefix),
same convention live_client.py documents for the Voice Agent/Streaming
APIs. Uses only the standard library (urllib), matching this repo's
standard-library-only build constraint (see live_client.py's docstring).

This module never logs, prints, or writes the API key anywhere -- it only
ever places it in the outgoing request header.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from voice_honesty_gate.errors import NoApiKeyError
from voice_honesty_gate.live_client import DEFAULT_KEY_PATH, read_api_key

UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"


def _auth_headers(api_key: str, content_type: str | None = None) -> dict[str, str]:
    headers = {"authorization": api_key}
    if content_type:
        headers["content-type"] = content_type
    return headers


def upload_file(audio_path: Path | str, api_key: str | None = None, key_path: Path | str = DEFAULT_KEY_PATH) -> dict[str, Any]:
    """POST the raw bytes of `audio_path` to /v2/upload. Returns the parsed
    JSON response ({"upload_url": "..."}). Raises NoApiKeyError if no key is
    available -- never makes the network call without one."""
    key = api_key or read_api_key(key_path)
    if not key:
        raise NoApiKeyError(f"no AssemblyAI API key found at {key_path!s}")

    data = Path(audio_path).read_bytes()
    req = urllib.request.Request(
        UPLOAD_URL,
        data=data,
        headers=_auth_headers(key, "application/octet-stream"),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def submit_transcript(audio_url: str, api_key: str | None = None, key_path: Path | str = DEFAULT_KEY_PATH) -> dict[str, Any]:
    """POST {"audio_url": ...} to /v2/transcript. Returns the parsed JSON
    response (carries "id" and initial "status")."""
    key = api_key or read_api_key(key_path)
    if not key:
        raise NoApiKeyError(f"no AssemblyAI API key found at {key_path!s}")

    body = json.dumps({"audio_url": audio_url}).encode("utf-8")
    req = urllib.request.Request(
        TRANSCRIPT_URL,
        data=body,
        headers=_auth_headers(key, "application/json"),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_transcript(transcript_id: str, api_key: str | None = None, key_path: Path | str = DEFAULT_KEY_PATH) -> dict[str, Any]:
    """GET /v2/transcript/{id} once. Returns the parsed JSON response."""
    key = api_key or read_api_key(key_path)
    if not key:
        raise NoApiKeyError(f"no AssemblyAI API key found at {key_path!s}")

    req = urllib.request.Request(
        f"{TRANSCRIPT_URL}/{transcript_id}",
        headers=_auth_headers(key),
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def transcribe_and_wait(
    audio_path: Path | str,
    api_key: str | None = None,
    key_path: Path | str = DEFAULT_KEY_PATH,
    poll_interval_s: float = 3.0,
    max_polls: int = 20,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Run the full upload -> submit -> poll-until-completed sequence for one
    audio file. Returns (upload_response, submit_response, poll_responses)
    where poll_responses is every GET response observed, in order, ending
    with the first "completed" or "error" status. Raises RuntimeError if
    max_polls is exhausted without reaching a terminal status.
    """
    key = api_key or read_api_key(key_path)
    if not key:
        raise NoApiKeyError(f"no AssemblyAI API key found at {key_path!s}")

    upload_resp = upload_file(audio_path, api_key=key, key_path=key_path)
    submit_resp = submit_transcript(upload_resp["upload_url"], api_key=key, key_path=key_path)
    transcript_id = submit_resp["id"]

    polls: list[dict[str, Any]] = []
    for _ in range(max_polls):
        poll_resp = get_transcript(transcript_id, api_key=key, key_path=key_path)
        polls.append(poll_resp)
        if poll_resp.get("status") in ("completed", "error"):
            return upload_resp, submit_resp, polls
        time.sleep(poll_interval_s)

    raise RuntimeError(
        f"transcript {transcript_id!r} did not reach a terminal status after {max_polls} polls"
    )
