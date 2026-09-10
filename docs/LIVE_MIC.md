# AssemblyAI Streaming Speech-to-Text — live microphone notes

Fetched live via WebFetch on **2026-09-09** (same session as `API_NOTES.md`,
which already carried some of this from the getting-started page; this file
re-fetches and adds the pieces `live` mode actually needs: chunk size, how
audio bytes go over the wire, and the streaming pricing line). Every quote
below names the URL it came from. One URL guessed first (the API-reference
path pattern used elsewhere in this repo) 404'd and is named as a dead end.

## WebSocket URL

`https://www.assemblyai.com/docs/speech-to-text/universal-streaming`:

> `"wss://streaming.assemblyai.com/v3/ws"` with query parameters for
> configuration.

Same URL `docs/API_NOTES.md` already recorded from the getting-started page
(`/docs/streaming/getting-started/transcribe-streaming-audio`) — two
different pages, same endpoint. `streaming_client.py` sets
`STREAMING_WS_URL = "wss://streaming.assemblyai.com/v3/ws"`, matching
`live_client.py`'s existing constant of the same name/value.

## Auth

`https://www.assemblyai.com/docs/speech-to-text/universal-streaming`:

> Authentication uses the `Authorization` header with your API key
> directly: `"header={"Authorization": API_KEY}"` with no `Bearer` prefix
> required.

Same convention every other client in this repo already uses
(`live_client.py`, `pre_recorded_client.py`).

## Audio format

`https://www.assemblyai.com/docs/speech-to-text/universal-streaming`:

> - **Default:** mono 16-bit PCM
> - **Sample rate:** configurable via `sample_rate` parameter to match
>   your source
> - **Supported encodings:** AAC (`encoding=aac` with ADTS framing), Opus
>   (`encoding=ogg_opus` for Ogg streams, `encoding=opus` for raw packets)
> - **Chunk size:** `4096` bytes per iteration shown in examples

`docs/API_NOTES.md`'s earlier fetch of the same page's query-parameter
table separately recorded `speech_model` (example `"universal-3-5-pro"`) as
an optional third query parameter alongside `encoding` and `sample_rate`.
A follow-up fetch aimed at the page's worked Python example returned:

> The example uses this exact endpoint: `wss://streaming.assemblyai.com/v3/ws?speech_model=universal-3-5-pro&encoding=aac`
> ... "set `sample_rate` to match your source." However, the specific
> example shown does not include `sample_rate` as a query parameter, only
> `speech_model` and `encoding`. ... Chunk size: "4096" bytes per
> iteration.

That worked example streams AAC from an internet radio URL, not a
microphone, so its own query string (`encoding=aac`, no `sample_rate`)
does not apply to this build. `streaming_client.py` instead uses the
**default mono 16-bit PCM** path (omits `encoding` entirely — the "Default:
mono 16-bit PCM" line above — and always sends `sample_rate` explicitly,
per "configurable via `sample_rate` parameter to match your source"),
because raw PCM is what `sounddevice`'s `InputStream` and the stdlib `wave`
module both hand back with no extra encoding step. Chunk size: this build
reuses the documented `4096` bytes/iteration.

**Least-certain fact #1**: the page's own example never actually streams
raw PCM query-string-only (its shown example is AAC-from-radio), so "omit
`encoding` for default PCM16" is this build's own reading of the "Default:
mono 16-bit PCM" line, not a quoted worked example for the PCM case
specifically. `streaming_client.py`'s connection is proven end-to-end
against AssemblyAI in `LIVE_MIC_RECEIPT.md` before this is fully trusted.

## Sending audio

`https://www.assemblyai.com/docs/speech-to-text/universal-streaming`:

> Audio is sent as binary frames: `"ws.send(chunk, websocket.ABNF.OPCODE_BINARY)"`
> rather than JSON-wrapped base64.

`streaming_client.py` sends each raw PCM16LE chunk as a binary WebSocket
message (`websockets` package: `ws.send(chunk)` with `chunk: bytes` sends a
binary frame automatically — the same wire behaviour the quoted
`ABNF.OPCODE_BINARY` call produces in the docs' own `websocket-client`
example, just via a different Python library).

**Least-certain fact #2**: the doc's own example never states a sleep/
delay between chunk sends ("Delay between sends: None documented; chunks
are sent immediately in a loop" — the radio-stream example just drains the
source as fast as it decodes). For a live microphone this build paces
sends to real wall-clock chunk duration (`sounddevice` naturally does this
via its callback; the `--from-wav` path sleeps
`len(chunk_bytes) / (sample_rate * 2)` seconds between sends) rather than
bursting the whole file — a documented recommendation was not found either
way, so this is this build's own choice, stated as such, not attributed to
AssemblyAI.

## Message types — partial and final turns

`https://www.assemblyai.com/docs/speech-to-text/universal-streaming`
(cross-checked against `docs/API_NOTES.md`'s earlier, more detailed fetch
of the same page):

> **Begin event (session opens):** `"{ "type": "Begin", "id": "...", "expires_at": ... }"`
>
> **Turn event (transcription updates):** `"{ "type": "Turn", "turn_order": 0, "end_of_turn": true, "transcript": "...", "words": [...] }"`
> — `end_of_turn: true` marks finalized turns
>
> **Termination event (session closes):** `"{ "type": "Termination", "audio_duration_seconds": 10, "session_duration_seconds": 12 }"`

`API_NOTES.md`'s original fetch additionally recorded `turn_is_formatted`
and `end_of_turn_confidence` fields on the same `Turn` event and a
`Terminate` client message (`{"type": "Terminate"}`) — this build's
`streaming_client.py` reads `type`, `end_of_turn`, and `transcript` off
every `Turn` event: a `Turn` with `end_of_turn: false` is a **partial**
(printed to the terminal, not appended to the accumulating transcript or
checked); a `Turn` with `end_of_turn: true` is a **final** (printed, and
appended for the honesty check).

**Least-certain fact #3**: nothing quoted above (either fetch) states
whether `Turn` events with `end_of_turn: false` (partials) share the same
`turn_order` as the final that follows them, or whether a session can emit
more than one final per `turn_order`. `streaming_client.py` treats every
`end_of_turn: true` Turn as one appended line regardless of `turn_order`,
which is the conservative reading and was not falsified by the one real
run recorded in `LIVE_MIC_RECEIPT.md`.

## Session termination

Same page:

> **Session Termination**: Send a JSON message to end the session:
> `"ws.send(json.dumps({"type": "Terminate"}))"`. The documentation notes:
> "Keep the connection open long enough to receive the last final."

`streaming_client.py` sends `{"type": "Terminate"}` after the audio source
is exhausted (WAV end, or `--seconds` elapsed) and then keeps reading
frames for up to 5 seconds waiting for the last `Turn`/`Termination`
message before closing, per that instruction.

## Pricing (streaming specifically)

`https://www.assemblyai.com/pricing`:

> - **Universal-3.5 Pro Realtime** (`u3-rt-pro`): **$0.45/hr**
> - **Universal-Streaming English** (`universal-streaming-english`): **$0.15/hr**
> - **Universal-Streaming Multilingual** (`universal-streaming-multilingual`): **$0.15/hr**
>
> "Session duration, not audio duration. A WebSocket open for 60 minutes
> with 30 minutes of audio sent is billed for 60 minutes." ... "Always
> close the WebSocket immediately when a call ends" ... Free-tier streaming
> concurrency: 5 new streams per minute. The free $50 credit applies across
> all AssemblyAI products, but streaming access is throttled at signup
> unless you move to a paid account (which allows 100 new streams per
> minute).

`streaming_client.py` does not pass a `speech_model` query parameter (the
account default model applies), so the applicable rate for the one real
run in `LIVE_MIC_RECEIPT.md` is the account's default streaming model —
named there against **session duration**, per the billing rule quoted
above, not audio duration.

## Dead ends (guessed first, both 404'd)

- `https://www.assemblyai.com/docs/api-reference/streaming/websocket` — 404
  (guessed by analogy to this repo's other REST endpoints' URL shape).
- `/docs/voice-agent` and `/docs/api-reference/streaming-api` — already
  named as dead ends in `API_NOTES.md` from the earlier session.

## What this file's fetches did NOT need to answer

`live_client.py`'s Voice Agent product (`tool.call`/`tool.result`/
`transcript.agent` over `agents.assemblyai.com`) is a **different**
AssemblyAI product from the Streaming Speech-to-Text product this file
documents (`streaming.assemblyai.com/v3/ws`, plain `Turn` events, no tool
schema). `cli.py live` mode uses the Streaming product only — the tool-call
side of the honesty check comes from `--tool-log` (this build's own file,
not an AssemblyAI event), exactly per the goal's command shape. See
`streaming_client.py`'s module docstring for the same split stated in code.
