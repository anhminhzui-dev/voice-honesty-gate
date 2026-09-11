"""Live-call adapter for AssemblyAI's Voice Agent API.

Endpoint, auth, and event shapes below are quoted and cited in full in
docs/API_NOTES.md (fetched from assemblyai.com/docs on 2026-09-09); this
module does not invent anything not sourced there.

  REST base   https://agents.assemblyai.com/v1   (POST /agents, GET /sessions, GET /sessions/$ID)
  Auth        header "Authorization: <api key>" (no "Bearer" prefix)
  Streaming   wss://streaming.assemblyai.com/v3/ws  (raw audio -> transcript, RFC 6455 WebSocket)

Build constraint for this hackathon scaffold: no paid API call, no account
sign-up. The key is supplied later at the path named by the
``ASSEMBLYAI_KEY_FILE`` env var (default ``~/.config/voice-honesty-gate/
assemblyai.key``); read_api_key() looks there and
returns None if it is absent, which is the designed-for state today, not
an error -- callers (the CLI, tests) fall back to fixture mode against a
saved transcript instead.

The two pieces below are real, not stubs, and are exercised by
tests/test_live_client.py without any network access:

  * `compute_ws_accept_key` -- the RFC 6455 handshake's Sec-WebSocket-Accept
    computation, checked against the worked example IN THE RFC ITSELF
    (section 1.3): key "dGhlIHNhbXBsZSBub25jZQ==" must accept as
    "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=".
  * `encode_client_frame` / `decode_server_frame` -- masked-client/
    unmasked-server WebSocket text-frame framing, checked by round-trip.

`AssemblyAIVoiceAgentClient.connect()` performs the actual TLS socket
connect and HTTP Upgrade handshake using only `socket`/`ssl` (no
third-party WebSocket library, per the standard-library-only build
constraint). It is NOT exercised by any test in this repository -- doing
so needs a real API key and a live AssemblyAI session, which this build
does not have. See BUILD_RECEIPT.md for exactly what remains untested
pending the key.
"""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import ssl
import struct
from pathlib import Path
from typing import Iterator

from voice_honesty_gate.errors import NoApiKeyError

REST_BASE_URL = "https://agents.assemblyai.com/v1"
STREAMING_WS_URL = "wss://streaming.assemblyai.com/v3/ws"
STREAMING_WS_HOST = "streaming.assemblyai.com"
STREAMING_WS_PATH = "/v3/ws"

DEFAULT_KEY_PATH = Path(
    os.environ.get("ASSEMBLYAI_KEY_FILE", "~/.config/voice-honesty-gate/assemblyai.key")
).expanduser()

# RFC 6455 section 1.3's fixed GUID, concatenated with the client's
# Sec-WebSocket-Key before SHA-1 + base64 to produce Sec-WebSocket-Accept.
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

_OPCODE_TEXT = 0x1
_OPCODE_CLOSE = 0x8


def read_api_key(path: Path | str = DEFAULT_KEY_PATH) -> str | None:
    """Return the AssemblyAI API key from `path`, stripped, or None if the
    file does not exist. Never raises for a missing file -- that is the
    expected pre-key state for this build.
    """
    p = Path(path)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8").strip()
    return text or None


def compute_ws_accept_key(sec_websocket_key: str) -> str:
    """RFC 6455 section 1.3 handshake: base64(sha1(key + GUID))."""
    digest = hashlib.sha1((sec_websocket_key + _WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def make_sec_websocket_key() -> str:
    """16 random bytes, base64-encoded, per RFC 6455 section 4.1."""
    return base64.b64encode(os.urandom(16)).decode("ascii")


def encode_client_frame(payload: bytes, opcode: int = _OPCODE_TEXT) -> bytes:
    """Encode one RFC 6455 WebSocket frame carrying `payload`. Client-to-
    server frames MUST be masked (RFC 6455 section 5.3); this always masks
    with a fresh random 4-byte key, single-frame (FIN=1), no fragmentation.
    Only handles payloads under 2**16 bytes (extended-length frames are not
    needed for this project's small JSON control/audio-chunk messages).
    """
    if len(payload) >= 65536:
        raise ValueError("encode_client_frame only supports payloads under 65536 bytes")

    fin_and_opcode = 0x80 | (opcode & 0x0F)
    mask_key = os.urandom(4)
    masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    length = len(payload)
    if length < 126:
        header = struct.pack("!BB", fin_and_opcode, 0x80 | length)
    else:
        header = struct.pack("!BBH", fin_and_opcode, 0x80 | 126, length)
    return header + mask_key + masked


def decode_server_frame(buf: bytes) -> tuple[int, bytes, int] | None:
    """Decode one RFC 6455 frame from the START of `buf`. Server-to-client
    frames are never masked (RFC 6455 section 5.1). Returns
    (opcode, payload, bytes_consumed), or None if `buf` does not yet hold a
    complete frame (caller should read more bytes and retry). Only handles
    the 7-bit and 16-bit extended length forms (sufficient for this
    project's small JSON event messages); a 64-bit extended-length frame
    raises ValueError rather than silently mis-parsing.
    """
    if len(buf) < 2:
        return None
    b0, b1 = buf[0], buf[1]
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F

    offset = 2
    if length == 126:
        if len(buf) < offset + 2:
            return None
        (length,) = struct.unpack("!H", buf[offset : offset + 2])
        offset += 2
    elif length == 127:
        raise ValueError("decode_server_frame does not support 64-bit extended-length frames")

    mask_key = b""
    if masked:
        if len(buf) < offset + 4:
            return None
        mask_key = buf[offset : offset + 4]
        offset += 4

    if len(buf) < offset + length:
        return None
    payload = buf[offset : offset + length]
    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return opcode, payload, offset + length


class AssemblyAIVoiceAgentClient:
    """Real (not stubbed) client for AssemblyAI's streaming WebSocket
    endpoint, gated on an API key being present at `key_path`. Construction
    raises NoApiKeyError, not a network call, when the key is absent --
    callers should catch that and fall back to fixture mode.
    """

    def __init__(self, api_key: str | None = None, key_path: Path | str = DEFAULT_KEY_PATH) -> None:
        self.api_key = api_key or read_api_key(key_path)
        if not self.api_key:
            raise NoApiKeyError(
                f"no AssemblyAI API key found at {key_path!s}. This build makes no paid API call and no "
                "account sign-up: run in fixture mode instead (`vhg check <transcript.json>`) until the "
                "Founder places a key at that path."
            )

    def connect(self, timeout: float = 10.0) -> ssl.SSLSocket:
        """Open a TLS connection to STREAMING_WS_HOST and perform the RFC
        6455 HTTP Upgrade handshake against STREAMING_WS_PATH, authorised
        per docs/API_NOTES.md ("Authorization" header, no Bearer prefix).
        Returns the raw connected+upgraded socket for the caller to read/
        write frames on with encode_client_frame/decode_server_frame.

        Not exercised by any test in this repository -- see this module's
        docstring and BUILD_RECEIPT.md.
        """
        sec_key = make_sec_websocket_key()
        raw_sock = socket.create_connection((STREAMING_WS_HOST, 443), timeout=timeout)
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(raw_sock, server_hostname=STREAMING_WS_HOST)

        request = (
            f"GET {STREAMING_WS_PATH} HTTP/1.1\r\n"
            f"Host: {STREAMING_WS_HOST}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Authorization: {self.api_key}\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))

        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("AssemblyAI streaming endpoint closed the connection during handshake")
            response += chunk

        header_text = response.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1")
        status_line = header_text.split("\r\n", 1)[0]
        if " 101 " not in status_line:
            raise ConnectionError(f"AssemblyAI streaming handshake failed: {status_line!r}")

        expected_accept = compute_ws_accept_key(sec_key)
        if expected_accept not in header_text:
            raise ConnectionError(
                "AssemblyAI streaming handshake response did not carry the expected Sec-WebSocket-Accept"
            )
        return sock

    def iter_frames(self, sock: ssl.SSLSocket, chunk_size: int = 4096) -> Iterator[tuple[int, bytes]]:
        """Yield (opcode, payload) for each complete frame read from `sock`,
        stopping on a close frame or a closed connection. Not exercised by
        any test (see connect()'s docstring)."""
        buf = b""
        while True:
            parsed = decode_server_frame(buf)
            if parsed is None:
                chunk = sock.recv(chunk_size)
                if not chunk:
                    return
                buf += chunk
                continue
            opcode, payload, consumed = parsed
            buf = buf[consumed:]
            if opcode == _OPCODE_CLOSE:
                return
            yield opcode, payload
