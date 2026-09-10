# AssemblyAI Voice Agent API — fetched notes

Fetched live via WebFetch against assemblyai.com/docs on **2026-09-09**. Every
quote below is the tool's direct extraction from the live page it names;
nothing here is drawn from training-data recall. Two pages returned 404 at
fetch time (`/docs/voice-agent`, `/docs/api-reference/streaming-api`) —
those exact paths are noted below as **dead** so nobody re-guesses them.

## Product surface

Fetching `https://www.assemblyai.com/docs` and asking it to list Voice
Agent / streaming / real-time / WebSocket references returned:

> **Voice Agent API** — URL: `/docs/voice-agents/voice-agent-api` —
> "A fully managed speech-to-speech pipeline — one connection handles STT,
> LLM reasoning, and TTS together at roughly one second end-to-end
> latency"
>
> **Streaming Speech-to-Text API** — URL:
> `/docs/streaming/getting-started/transcribe-streaming-audio` —
> "Handles live audio over WebSocket with ~150ms p50 latency, powering
> voice agents, live captions, and real-time agent-assist tools"

(`/docs/voice-agent` and `/docs/api-reference/streaming-api` — the two URL
guesses this session tried first — both 404. The correct paths carry the
`voice-agents` (plural) and `streaming/getting-started` segments above.)

## Voice Agent API — REST session management

Fetching `https://www.assemblyai.com/docs/voice-agents/voice-agent-api`:

> REST endpoints referenced: `https://agents.assemblyai.com/v1/sessions`
> (list sessions), `https://agents.assemblyai.com/v1/sessions/$SESSION_ID`
> (fetch session details), `POST /v1/agents` (create agent).
>
> Authentication: `"Authorization: $ASSEMBLYAI_API_KEY"` header format
> shown in curl examples for API calls.
>
> "Events reference" section at
> `/docs/voice-agents/voice-agent-api/events-reference` described as
> containing "every WebSocket event with full payloads."

This repo's `live_client.py` sets `REST_BASE_URL =
"https://agents.assemblyai.com/v1"` and the auth header as
`Authorization: <api key>` (no `Bearer` prefix, exactly as quoted) from
this.

## Voice Agent API — WebSocket events (client<->server)

Fetching `https://www.assemblyai.com/docs/voice-agents/voice-agent-api/events-reference`:

**Client -> Server**

```json
{ "type": "input.audio", "audio": "<base64-encoded PCM16>" }
{ "type": "session.update", "session": { "system_prompt": "...", "greeting": "...", "tools": [...] } }
{ "type": "session.resume", "session_id": "sess_abc123" }
{ "type": "session.end" }
{ "type": "tool.result", "call_id": "call_abc123", "result": "{...}", "is_error": false }
{ "type": "reply.create", "instructions": "..." }
{ "type": "conversation.message", "role": "user", "content": "..." }
```

**Server -> Client**

```json
{ "type": "session.ready", "session_id": "sess_abc123", "config": {...} }
{ "type": "input.speech.started" }
{ "type": "transcript.user.delta", "item_id": "item_abc123", "text": "..." }
{ "type": "transcript.user", "text": "...", "item_id": "item_abc123" }
{ "type": "tool.call", "call_id": "call_abc123", "name": "get_weather", "arguments": {...} }
{ "type": "reply.started", "reply_id": "reply_abc123", "item_id": "item_abc123" }
{ "type": "reply.done", "reply_id": "reply_abc123", "status": "completed" }
{ "type": "transcript.agent.delta", "reply_id": "reply_abc123", "delta": "sunny", "start_ms": 1200, "end_ms": 1560 }
{ "type": "transcript.agent", "text": "...", "reply_id": "reply_abc123", "interrupted": false }
{ "type": "session.error", "code": "invalid_format", "message": "..." }
```

This is the exact event vocabulary `src/voice_honesty_gate/adapter.py` is
written against: it reads `tool.call`, `tool.result`, and
`transcript.agent` events (the three the ported check needs — a tool the
agent invoked, its confirmed/error result, and the agent's own spoken
claim) and passes every other documented event through unread.

## Streaming Speech-to-Text API — raw WebSocket

Fetching `https://www.assemblyai.com/docs/streaming/getting-started/transcribe-streaming-audio`:

> **Endpoint URL** `"wss://streaming.assemblyai.com/v3/ws"` with query
> parameters appended via URL encoding.
>
> **Query parameters**: `speech_model` (example `"universal-3-5-pro"`),
> `encoding` (example `"aac"` for AAC/ADTS, `"ogg_opus"` for Ogg streams,
> `"opus"` for raw packets), `sample_rate` (optional, to match audio
> source).
>
> **Authentication**: `"Authorization"` header containing the API key
> directly — no `"Bearer"` prefix required.
>
> **Session Begin**: `{ "type": "Begin", "id": "...", "expires_at": "..." }`
>
> **Partial/Final Transcript (Turn)**:
> ```json
> {
>   "type": "Turn",
>   "turn_order": 0,
>   "end_of_turn": true,
>   "turn_is_formatted": true,
>   "end_of_turn_confidence": 1.0,
>   "transcript": "...",
>   "words": [{"text": "...", "start": 0, "end": 399, "confidence": 0.99}]
> }
> ```
> The `"end_of_turn": true` flag marks finalized turns.
>
> **Session Termination**: `{ "type": "Termination", "audio_duration_seconds": 10, "session_duration_seconds": 12 }`
>
> **Client Termination Message**: `{"type": "Terminate"}`

This is the source for `live_client.py`'s `STREAMING_WS_URL =
"wss://streaming.assemblyai.com/v3/ws"`, `STREAMING_WS_HOST =
"streaming.assemblyai.com"`, `STREAMING_WS_PATH = "/v3/ws"`, and the
`Authorization: <key>` header (no Bearer prefix) in
`AssemblyAIVoiceAgentClient.connect()`.

## What this build did NOT need to fetch

The RFC 6455 WebSocket handshake and frame-format constants
(`live_client.py`'s `_WS_GUID`, `compute_ws_accept_key`,
`encode_client_frame`, `decode_server_frame`) are IETF standard, not
AssemblyAI-specific — sourced from RFC 6455 itself (sections 1.3, 4.1,
5.1, 5.3), not fetched from AssemblyAI's docs. `compute_ws_accept_key` is
checked in `tests/test_live_client.py` against the RFC's own worked
example, independent of anything AssemblyAI publishes.

## Pre-recorded transcription API — upload + transcript (fetched 2026-09-09, live end-to-end call)

The Voice Agent WS and Streaming WS sections above are session/streaming
products; neither fits a one-shot "upload a WAV, get text back" call, which
is what the live end-to-end proof (`LIVE_RECEIPT.md`) actually needed. This
section's three endpoints were fetched live on 2026-09-09 (three additional
WebFetch calls, after `https://www.assemblyai.com/docs/api-reference`
pointed at `/docs/pre-recorded-audio/api-reference/files/upload` as the
entry point) and are the ones the live call in this build actually used.

**1. Upload a file** — `POST https://api.assemblyai.com/v2/upload`
Header `authorization: <API_KEY>` (no `Bearer` prefix, same convention as
the Voice Agent API above). Body: raw binary (`application/octet-stream`),
the WAV file bytes directly, not multipart/form. Response:
```json
{ "upload_url": "string" }
```
"A URL that points to your audio file, accessible only by AssemblyAI's
servers."

**2. Create a transcript** — `POST https://api.assemblyai.com/v2/transcript`
Header `authorization: <API_KEY>`, `content-type: application/json`. Body
requires only `audio_url` (the `upload_url` from step 1). Response carries
`id` (UUID), `status` (`queued`/`processing`/`completed`/`error`),
`audio_url`, `text` (null until completed).

**3. Get a transcript** — `GET https://api.assemblyai.com/v2/transcript/{transcript_id}`
Header `authorization: <API_KEY>`. Poll until `status` is `"completed"`
("The transcript is ready when the 'status' is 'completed'.") or `"error"`.
Completed response carries `text` (the transcript string), `confidence`,
`audio_duration`.

This build's live call used these three endpoints only, via
`src/voice_honesty_gate/pre_recorded_client.py` (stdlib `urllib`, no
third-party HTTP dependency, consistent with `live_client.py`'s
standard-library-only constraint). Raw JSON responses (upload response has
no key material; transcript responses carry no key material either — the
key only ever appears in the outgoing `authorization` request header,
never in any response body) are saved under `tests/fixtures/live/`.

## What is still open (not fabricated, not guessed)

Not fetched in this pass, because this build makes no paid API call and no
account sign-up (see BUILD_RECEIPT.md): the exact `tools` schema shape
inside `session.update` (how a tool's name/parameters are declared to the
agent — the events-reference excerpt above shows `"tools": [...]` without
expanding the array's element shape), and the audio encoding AssemblyAI's
Voice Agent product itself expects on `input.audio` versus the streaming
product's `encoding` query parameter. Both are needed before a real
`session.update` call could be sent; `live_client.py` does not send one.
