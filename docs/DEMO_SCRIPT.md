# Demo script (90 seconds, judges watching live)

Goal: the judge watches the agent say it finished something it did not
finish, and watches the gate catch it out loud. The pitch line from the
walkthrough carries the whole demo: "a gate that tells you when it cannot
see is more trustworthy than one that claims to see everything."

## Setup (before the judge is watching)

- Terminal open, `M:/AGENT_VAULT/PORTFOLIO/repos/voice-honesty-gate`
  current directory.
- Two saved transcripts staged: `tests/fixtures/booking_success.json`
  (honest — the agent really booked the table) and
  `tests/fixtures/claim_no_tool.json` (dishonest — the agent claims a
  cancellation it never attempted).
- If a real AssemblyAI key has landed by demo day, a live call replaces
  the staged transcripts (see "If the key has landed" below); if not, the
  fixture run below is the whole demo and is said out loud as such.

## 0:00 - 0:15 — the claim (spoken by the Founder)

"Voice agents are getting good at sounding certain. A user asks it to
book a table, cancel a flight, send an email — and the agent says 'done.'
The problem: 'done' is a claim, not a fact. Nothing today checks a voice
agent's spoken claim against what it actually did. We built the check."

## 0:15 - 0:40 — the honest booking (GO)

Run:

```
vhg check tests/fixtures/booking_success.json
```

Say while the JSON prints: "The agent booked a real table — you can see
the tool call and its confirmed result in the transcript — then said
'done.' The gate reads that as GO: the claim is backed by a step that
actually completed." Point at the printed `"coverage": {"status": "ALIVE"}`
line: "and it tells you it actually looked — not just that nothing was
wrong."

## 0:40 - 1:05 — the false claim (HOLD, the money shot)

Run:

```
vhg check tests/fixtures/claim_no_tool.json
```

Say while the JSON prints: "Same wording, same confidence — 'Done, I've
cancelled your flight' — except this time the agent never called a
booking tool at all. No tool call, no result, nothing. The gate holds it:
`FALSE_COMPLETION_CLAIM`, 'no tool was ever called in this session.' That
is the exact lie a user on the phone would have trusted."

## 1:05 - 1:25 — the honest numbers (the credibility line)

"This check is a port of a check we already proved on 300 real coding-
agent trajectories — caught 100% of the eligible cases there. On real
human-labelled deception data it is much weaker: 28.6% recall on one set,
6.25% on another. We say that up front because a gate that hides its own
blind spots is worse than one that has none. The coverage line you saw —
ALIVE, DEAD — is that same honesty, per call: it tells you exactly when it
had nothing to check against, instead of pretending it saw everything."

## 1:25 - 1:30 — close

"Free, deterministic, zero network calls to get this far. The only thing
between this and a live phone call is AssemblyAI's key — which is exactly
where this demo picks up next."

## If the key has landed by demo day

Replace both `vhg check` runs above with one real end-to-end call: connect
`AssemblyAIVoiceAgentClient`, run a short live voice session that
deliberately claims completion without a backing tool call, save the
transcript, then run `vhg check` on the saved file exactly as above. Say
so explicitly: "this is a real AssemblyAI Voice Agent call, not a canned
file" — the two questions judges ask (see the walkthrough) are answered by
this line alone, spoken honestly either way.
