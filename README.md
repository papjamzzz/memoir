<p align="center">
  <img src="static/logo.png" width="120" alt="Memoir logo"/>
</p>

# Memoir — Voice-to-Story AI Journaling

> **Speak your story. AI structures it, preserves it, gives it back.**

Voice-first journaling that turns spoken thoughts into organized, searchable life documentation. No typing. No formatting. Talk like you're calling a friend — Memoir handles everything else.

**Live:** [memoir.creativekonsoles.com](https://memoir.creativekonsoles.com)

---

## What It Does

- **Voice input** — speak naturally, no formatting or structure required
- **AI structuring** — Claude processes your words into clean, organized entries with themes, emotions, and context
- **Timeline view** — your life, organized chronologically and searchable
- **Privacy-first** — your data stays on your machine, never shared
- **Export** — download your full memoir at any time

---

## How It Works

```
You speak into the browser mic
  ↓ Web Speech API transcribes in real time
  ↓ POST /api/entry → Claude (Anthropic)
  ↓ Claude structures the entry: title, themes, emotions, narrative
  ↓ Saved to local database
  ↓ Appears in timeline view
```

---

## Use Cases

- Daily journaling without the friction of typing
- Life documentation for people with memory or cognitive challenges
- Legacy writing — record stories for family
- Therapy support — structured emotional processing between sessions

---

## Stack

Python · Flask · Claude (Anthropic) · Vanilla JS · Web Speech API · SQLite · Railway

---

## Setup

```bash
git clone https://github.com/papjamzzz/memoir.git
cd memoir
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
make setup
make run
```

Opens at `http://127.0.0.1:5565`

Or double-click `launch.command` on Mac.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Powers AI structuring via Claude |

---

## Part of Creative Konsoles

Built by [Creative Konsoles](https://creativekonsoles.com) — tools built using thought.

**[creativekonsoles.com](https://creativekonsoles.com)** &nbsp;·&nbsp; support@creativekonsoles.com

<!-- repo maintenance: 2026-05-12 -->
