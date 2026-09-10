---
title: Voice Honesty Gate
emoji: 🎙️
colorFrom: red
colorTo: gray
sdk: gradio
sdk_version: 6.26.0
app_file: app.py
pinned: false
license: mit
---

# Voice Honesty Gate — online demo

A voice-agent honesty gate for the AssemblyAI Voice Agent Hackathon
(lablab.ai, Sep 1-30 2026). Ports
[relay-gate](https://github.com/)'s `FALSE_COMPLETION_CLAIM` check —
already tested on 7,293 real coding-agent trajectories — to a live
AssemblyAI-transcribed spoken claim. A spoken "done" that no tool call
backs up gets held, out loud.

Record or upload audio, pick what the agent's tool-call log actually
shows ("no tool ran" or "booking tool ran and confirmed"), press **Run**.
No microphone? Press one of the two example buttons — they replay this
build's own live AssemblyAI fixture clips and show **HOLD** and **GO** in
two clicks.

This demo calls AssemblyAI's real pre-recorded transcription REST API
(`/v2/upload`, `/v2/transcript`) — the same client and endpoints this
repo's `LIVE_RECEIPT.md` used for its own live proof on 2026-09-09 — then
runs the ported honesty check unmodified.

**Honest limits (verbatim, this repo's `README.md`):** Zero of these
numbers is the check's recall on real human-labelled deception — that
measurement (relay-gate's own MAST/AgentRewardBench calibration: 28.6%
and 6.25% recall) is inherited unchanged, not re-measured for voice, and
is stated as such below. Verdict: FRONTIER, for the pre-recorded-
transcription proof; BASELINE still stands for the Voice Agent WebSocket
product itself.

## Deploy to Hugging Face Spaces (free, manual, Founder-gated)

This app is not deployed anywhere yet. When the Founder says go:

1. **Create the Space.** On huggingface.co, click "New Space" -> pick an
   owner + a name (e.g. `voice-honesty-gate`) -> SDK: **Gradio** -> Space
   hardware: **CPU basic (free)** -> Create Space.
2. **Add the API key as a Space secret.** In the new Space's Settings ->
   "Variables and secrets" -> "New secret" -> name it exactly
   `ASSEMBLYAI_API_KEY` -> paste the key value (never commit it to any
   file) -> Save. `webdemo/app.py`'s `get_api_key()` reads this
   environment variable first, before falling back to the repo's own
   `M:/AGENT_VAULT/secrets/assemblyai.key` file path (which does not exist
   on the Space's filesystem, by design — the Space never sees that
   drive).
3. **Upload the files.** In the Space's "Files" tab (or via
   `git push`/the `huggingface_hub` Python client), upload, preserving
   this exact relative layout so `webdemo/app.py`'s own `src/` and
   `relay-gate` sys.path wiring still resolves:
   - `webdemo/app.py` (rename to `app.py` at the Space root, since
     `app_file: app.py` above expects it there — or keep the `webdemo/`
     path and set `app_file: webdemo/app.py` in this file's front-matter
     instead, whichever the Space UI's upload step makes easier)
   - `webdemo/requirements.txt` (Spaces auto-installs from a
     `requirements.txt` at the repo root, so copy or symlink it there)
   - the whole `src/voice_honesty_gate/` package
   - the whole `relay-gate/src/relay_gate/` package (voice_honesty_gate
     imports it BY PATH, not pip — see
     `src/voice_honesty_gate/__init__.py`'s docstring; either upload
     `relay-gate/` as a sibling directory in the same Space repo, or set
     the `VHG_RELAY_GATE_SRC` environment variable/Space secret to
     wherever it ends up)
   - `tests/fixtures/audio/false_claim_no_tool.wav` and
     `tests/fixtures/audio/confirmed_tool_result.wav` (the two example
     clips the "Example" buttons load)
4. **Wait for the build, then open the Space.** The Space rebuilds
   automatically on file changes; the "App" tab shows build logs and,
   once green, the running demo at its own public URL
   (`https://huggingface.co/spaces/<owner>/<name>`) — that URL is what
   goes in lablab.ai's "Application URL" field.

Four steps, no paid tier required (CPU basic Spaces are free; the only
paid element is AssemblyAI's own per-call usage, already budgeted in
`LIVE_RECEIPT.md`).
