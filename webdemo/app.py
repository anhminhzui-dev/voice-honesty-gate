"""Gradio online demo for voice-honesty-gate.

lablab.ai's submission guide requires "a working prototype of your project
that others will be able to use online" and a "Demo application platform" /
"Application URL". This file is that demo: a Gradio UI a judge can run
locally today (`python webdemo/app.py`, see run_local.ps1) and deploy to a
free Hugging Face Space the moment the Founder says go (see
README_SPACE.md for the exact steps).

It does not reimplement the check. It reuses, unmodified:

  * `voice_honesty_gate.pre_recorded_client.transcribe_and_wait` -- the
    EXISTING AssemblyAI pre-recorded transcription REST client (upload ->
    submit -> poll), the same one `scripts/run_live_call.py` and
    `LIVE_RECEIPT.md`'s live proof used.
  * `voice_honesty_gate.live_client.read_api_key` -- the EXISTING key
    reader (checks `M:/AGENT_VAULT/secrets/assemblyai.key` by default).
    This app additionally checks the `ASSEMBLYAI_API_KEY` environment
    variable FIRST, because a Hugging Face Space has no M: drive -- a
    Space secret arrives as an env var, never as a file on disk.
  * `voice_honesty_gate.adapter.events_to_trajectory` -- the EXISTING
    AssemblyAI-event-shape -> relay_gate.schema.Trajectory adapter.
  * `voice_honesty_gate.voice_rules.check_voice_false_completion_claim` --
    the EXISTING ported honesty check.
  * `voice_honesty_gate.coverage.voice_coverage` -- the EXISTING
    ALIVE/DEAD coverage verdict.

This module's own job is small and new: turn one dropdown choice ("no tool
ran (liar)" / "booking tool ran and confirmed (honest)") into the
`tool.call`/`tool.result` events that belong around AssemblyAI's real
transcribed text, mirroring exactly how LIVE_RECEIPT.md's own
`tests/fixtures/live_confirmed_booking.json` / `live_false_claim.json`
were hand-built around real transcribed text (see LIVE_RECEIPT.md, "How
the two transcripts were built") -- and the exact same decision
computation `cli.py`'s `_run_check` already runs (GO / HOLD /
AMBIGUOUS-HOLD from the findings' categories), reproduced here because
`cli.py` operates on a saved-file path, not an in-memory trajectory built
from a live transcription result.

Never prints or logs the API key. The key is only ever passed to
`transcribe_and_wait`, which places it in the outgoing request header (see
`pre_recorded_client.py`'s own docstring guarantee).
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

WEBDEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEBDEMO_DIR.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from voice_honesty_gate.adapter import events_to_trajectory  # noqa: E402
from voice_honesty_gate.coverage import voice_coverage  # noqa: E402
from voice_honesty_gate.errors import MalformedTranscriptError, NoApiKeyError  # noqa: E402
from voice_honesty_gate.live_client import DEFAULT_KEY_PATH, read_api_key  # noqa: E402
from voice_honesty_gate.pre_recorded_client import transcribe_and_wait  # noqa: E402
from voice_honesty_gate.voice_rules import check_voice_false_completion_claim  # noqa: E402

# Dropdown choices -- exact strings named in this build's brief.
LIAR_LABEL = "no tool ran (liar)"
HONEST_LABEL = "booking tool ran and confirmed (honest)"
ACTION_LOG_CHOICES = [LIAR_LABEL, HONEST_LABEL]

# The repo's existing live fixture clips proving a real AssemblyAI call
# (LIVE_RECEIPT.md, 2026-09-09). tests/fixtures/live/ holds the raw
# AssemblyAI JSON records of that call; the WAV audio those records point
# at (see each record's "audio_path" field) lives under
# tests/fixtures/audio/ -- this app reads those WAVs for the two one-click
# examples so a judge with no microphone sees GO and HOLD in two clicks.
FIXTURES_AUDIO_DIR = REPO_ROOT / "tests" / "fixtures" / "audio"
EXAMPLE_LIAR_WAV = FIXTURES_AUDIO_DIR / "false_claim_no_tool.wav"
EXAMPLE_HONEST_WAV = FIXTURES_AUDIO_DIR / "confirmed_tool_result.wav"

# README.md's own calibration lines ("Frontier bar" -> "THE MEASUREMENT"
# row), copied verbatim -- the honest limits this demo must not round up.
README_CALIBRATION_LINE = (
    "Zero of these numbers is the check's recall on real human-labelled "
    "deception \u2014 that measurement (relay-gate's own MAST/"
    "AgentRewardBench calibration: 28.6% and 6.25% recall) is inherited "
    "unchanged, not re-measured for voice, and is stated as such below."
)
README_VERDICT_LINE = (
    "FRONTIER, for the pre-recorded-transcription proof; BASELINE still "
    "stands for the Voice Agent WebSocket product itself."
)


def get_api_key() -> str | None:
    """ASSEMBLYAI_API_KEY env var first (how a Hugging Face Space secret
    arrives), then the repo's existing file-based read_api_key() (how the
    Founder's own machine has the key today). Never prints either."""
    env_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if env_key:
        return env_key.strip() or None
    return read_api_key(DEFAULT_KEY_PATH)


def build_events(agent_action_log: str, agent_text: str) -> list[dict[str, Any]]:
    """Turn the dropdown choice + a transcribed claim into the AssemblyAI
    Voice Agent event shape adapter.py reads (see its module docstring).
    HONEST_LABEL prepends a confirmed tool.call/tool.result pair, exactly
    mirroring tests/fixtures/live_confirmed_booking.json's construction
    (LIVE_RECEIPT.md, "How the two transcripts were built"). LIAR_LABEL
    emits zero tool events, mirroring live_false_claim.json.
    """
    if agent_action_log not in ACTION_LOG_CHOICES:
        raise ValueError(
            f"unknown agent action log option {agent_action_log!r}; expected one of {ACTION_LOG_CHOICES!r}"
        )

    events: list[dict[str, Any]] = []
    if agent_action_log == HONEST_LABEL:
        events.append(
            {
                "type": "tool.call",
                "call_id": "call_webdemo_1",
                "name": "book_appointment",
                "arguments": {"date": "2026-09-15"},
            }
        )
        events.append(
            {
                "type": "tool.result",
                "call_id": "call_webdemo_1",
                "result": '{"status": "confirmed", "appointment_id": "A-WEBDEMO"}',
                "is_error": False,
            }
        )
    events.append(
        {
            "type": "transcript.agent",
            "text": agent_text,
            "reply_id": "reply_webdemo_1",
            "interrupted": False,
        }
    )
    return events


def decide(trajectory) -> tuple[str, list[dict[str, Any]], Any]:
    """Same GO / HOLD / AMBIGUOUS-HOLD computation cli.py's _run_check runs
    on findings' categories -- reproduced here (not imported) because
    cli.py's _run_check takes a file path, not an in-memory trajectory
    built from a live transcription result."""
    findings = check_voice_false_completion_claim(trajectory)
    cov = voice_coverage(trajectory)

    hold = [f for f in findings if f.category == "hold"]
    ambiguous = [f for f in findings if f.category == "ambiguous"]
    if hold:
        decision = "HOLD"
    elif ambiguous:
        decision = "AMBIGUOUS-HOLD"
    else:
        decision = "GO"

    findings_out = [
        {"code": f.reason.value, "category": f.category, "detail": f.detail} for f in findings
    ]
    return decision, findings_out, cov


def run_gate(
    audio_path: str,
    agent_action_log: str,
    transcribe_fn: Callable[[str, str | None], str] | None = None,
    api_key: str | None = None,
    session_id: str = "webdemo-session",
) -> dict[str, Any]:
    """The demo's core function: transcript in, decision out. Never touches
    the network itself -- `transcribe_fn` does that (default: real
    AssemblyAI via `_default_transcribe`). Tests pass a stub here so the
    HOLD/GO logic is checked with zero network access (see
    tests/test_webdemo.py).
    """
    if transcribe_fn is None:
        transcribe_fn = _default_transcribe

    transcript_text = transcribe_fn(audio_path, api_key)

    events = build_events(agent_action_log, transcript_text)
    try:
        trajectory = events_to_trajectory(session_id, events)
    except MalformedTranscriptError as exc:  # pragma: no cover -- events built above are always well-formed
        return {
            "session_id": session_id,
            "transcript": transcript_text,
            "decision": "ERROR",
            "findings": [],
            "coverage": None,
            "error": str(exc),
        }

    decision, findings_out, cov = decide(trajectory)

    return {
        "session_id": session_id,
        "transcript": transcript_text,
        "decision": decision,
        "findings": findings_out,
        "coverage": {
            "check": cov.check,
            "status": cov.status,
            "field": cov.field,
            "detail": cov.detail,
        },
        "error": None,
    }


def _default_transcribe(audio_path: str, api_key: str | None = None) -> str:
    """Real AssemblyAI pre-recorded transcription call via the repo's
    existing pre_recorded_client.transcribe_and_wait. Raises NoApiKeyError
    (caught by the UI wrapper below) if no key is configured."""
    key = api_key or get_api_key()
    if not key:
        raise NoApiKeyError(
            f"no AssemblyAI API key found (checked ASSEMBLYAI_API_KEY env var and {DEFAULT_KEY_PATH!s})"
        )
    _upload, _submit, polls = transcribe_and_wait(audio_path, api_key=key)
    final = polls[-1]
    if final.get("status") == "error":
        raise RuntimeError(f"AssemblyAI transcription error: {final.get('error')!r}")
    return str(final.get("text") or "")


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


def _decision_markdown(decision: str) -> str:
    color = {"GO": "#1a7f37", "HOLD": "#b91c1c", "AMBIGUOUS-HOLD": "#b45309", "ERROR": "#b91c1c"}.get(
        decision, "#374151"
    )
    return f"<div style='font-size:64px;font-weight:800;color:{color};text-align:center'>{decision}</div>"


def _finding_summary(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "No finding -- the spoken claim is backed by a confirmed tool result (or made no completion claim)."
    lines = []
    for f in findings:
        lines.append(f"{f['code']} ({f['category']}): {f['detail']}")
    return "\n\n".join(lines)


def run_gate_ui(audio_path: str | None, agent_action_log: str):
    if not audio_path:
        empty = {"error": "no audio provided"}
        return "", _decision_markdown("ERROR"), "No audio was provided -- record or upload a clip, or press an example button.", empty

    try:
        result = run_gate(audio_path, agent_action_log)
    except NoApiKeyError as exc:
        empty = {"error": str(exc)}
        return "", _decision_markdown("ERROR"), str(exc), empty
    except Exception as exc:  # noqa: BLE001 -- surface any transcription/network failure to the judge, not a stack trace
        empty = {"error": str(exc)}
        return "", _decision_markdown("ERROR"), f"transcription/check failed: {exc}", empty

    transcript = result["transcript"]
    decision_md = _decision_markdown(result["decision"])
    finding_text = _finding_summary(result["findings"])
    return transcript, decision_md, finding_text, result


def _load_example(wav_path: Path, label: str) -> tuple[str, str]:
    return str(wav_path), label


def build_demo():
    import gradio as gr

    with gr.Blocks(title="Voice Honesty Gate") as demo:
        gr.Markdown(
            "# Voice Honesty Gate\n"
            "Ports relay-gate's `FALSE_COMPLETION_CLAIM` check to a live AssemblyAI-transcribed "
            "spoken claim. Record or upload audio, pick what the agent's tool log actually shows, "
            "and press **Run**. A spoken \"done\" with no confirmed tool result is **HOLD**, out loud."
        )

        with gr.Row():
            with gr.Column(scale=1):
                audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Spoken claim (audio)")
                action_dropdown = gr.Dropdown(
                    choices=ACTION_LOG_CHOICES,
                    value=LIAR_LABEL,
                    label="Agent action log (what the tool-call trace actually shows)",
                )
                run_btn = gr.Button("Run", variant="primary")
                gr.Markdown("**No microphone? Try an example:**")
                with gr.Row():
                    liar_example_btn = gr.Button("Example: false claim, no tool ran -> expect HOLD")
                    honest_example_btn = gr.Button("Example: booking confirmed -> expect GO")

            with gr.Column(scale=1):
                decision_html = gr.HTML(_decision_markdown(""))
                transcript_box = gr.Textbox(label="Transcript (AssemblyAI)", lines=3)
                finding_box = gr.Textbox(label="Finding / reason", lines=4)
                raw_json = gr.JSON(label="Raw result JSON")

        run_btn.click(
            fn=run_gate_ui,
            inputs=[audio_input, action_dropdown],
            outputs=[transcript_box, decision_html, finding_box, raw_json],
        )
        liar_example_btn.click(
            fn=lambda: _load_example(EXAMPLE_LIAR_WAV, LIAR_LABEL),
            outputs=[audio_input, action_dropdown],
        ).then(
            fn=run_gate_ui,
            inputs=[audio_input, action_dropdown],
            outputs=[transcript_box, decision_html, finding_box, raw_json],
        )
        honest_example_btn.click(
            fn=lambda: _load_example(EXAMPLE_HONEST_WAV, HONEST_LABEL),
            outputs=[audio_input, action_dropdown],
        ).then(
            fn=run_gate_ui,
            inputs=[audio_input, action_dropdown],
            outputs=[transcript_box, decision_html, finding_box, raw_json],
        )

        gr.Markdown(
            f"---\n**Honest limits (verbatim, README.md \"Frontier bar\"):** {README_CALIBRATION_LINE}\n\n"
            f"**Verdict:** {README_VERDICT_LINE}"
        )

    return demo


def main() -> None:
    demo = build_demo()
    demo.launch()


if __name__ == "__main__":
    main()
