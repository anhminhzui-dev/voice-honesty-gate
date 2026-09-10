"""Pure-function tests for the WebSocket transport pieces in live_client.py.
No network access, no API key. These are the parts of the live-call
adapter that ARE proven to be correct without the key AssemblyAI has not
supplied yet; see live_client.py's module docstring for what remains
untested pending the key."""

import os

import pytest

import voice_honesty_gate  # noqa: F401
from voice_honesty_gate.errors import NoApiKeyError
from voice_honesty_gate.live_client import (
    AssemblyAIVoiceAgentClient,
    compute_ws_accept_key,
    decode_server_frame,
    encode_client_frame,
    read_api_key,
)


def test_ws_accept_key_matches_the_rfc6455_worked_example():
    """RFC 6455 section 1.3's own worked example: given
    Sec-WebSocket-Key "dGhlIHNhbXBsZSBub25jZQ==", the correct
    Sec-WebSocket-Accept is "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="."""
    assert compute_ws_accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_encode_client_frame_masks_the_payload_per_rfc6455():
    payload = b'{"type": "input.audio", "audio": "..."}'
    frame = encode_client_frame(payload)
    assert frame[1] & 0x80  # mask bit MUST be set on every client->server frame (RFC 6455 5.1)
    length = frame[1] & 0x7F
    assert length == len(payload)
    mask_key = frame[2:6]
    masked_payload = frame[6:]
    recovered = bytes(b ^ mask_key[i % 4] for i, b in enumerate(masked_payload))
    assert recovered == payload  # unmasking with the frame's own mask key recovers the original bytes


def test_decode_server_frame_parses_a_hand_built_unmasked_frame():
    # RFC 6455 5.1: server->client frames are never masked. Build one by
    # hand (FIN=1, opcode=text, mask bit unset, 7-bit length) independent
    # of encode_client_frame, to prove decode_server_frame's own parsing.
    payload = b'{"type": "session.ready", "session_id": "sess_abc"}'
    frame = bytes([0x81, len(payload)]) + payload
    decoded = decode_server_frame(frame)
    assert decoded is not None
    opcode, decoded_payload, consumed = decoded
    assert opcode == 0x1
    assert decoded_payload == payload
    assert consumed == len(frame)


def test_decode_server_frame_returns_none_on_incomplete_buffer():
    assert decode_server_frame(b"") is None
    assert decode_server_frame(bytes([0x81, 0x7E, 0x00])) is None  # extended-length header not fully read yet


def test_read_api_key_returns_none_when_file_absent(tmp_path):
    missing = tmp_path / "assemblyai.key"
    assert read_api_key(missing) is None


def test_read_api_key_reads_and_strips_file_contents(tmp_path):
    key_path = tmp_path / "assemblyai.key"
    key_path.write_text("  test-key-abc123  \n", encoding="utf-8")
    assert read_api_key(key_path) == "test-key-abc123"


def test_client_construction_raises_no_api_key_error_when_key_absent(tmp_path):
    missing = tmp_path / "assemblyai.key"
    with pytest.raises(NoApiKeyError):
        AssemblyAIVoiceAgentClient(key_path=missing)


def test_client_construction_succeeds_when_key_present(tmp_path):
    key_path = tmp_path / "assemblyai.key"
    key_path.write_text("test-key-abc123", encoding="utf-8")
    client = AssemblyAIVoiceAgentClient(key_path=key_path)
    assert client.api_key == "test-key-abc123"
