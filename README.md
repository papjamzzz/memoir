# Memoir — Voice-to-Story AI Journaling

**Speak your story. AI structures it, preserves it, gives it back to you.**

Memoir is a voice-first journaling tool that turns spoken thoughts into organized, searchable life documentation. Talk like you're calling a friend. Memoir handles the rest.

**Live:** [memoir.creativekonsoles.com](https://memoir.creativekonsoles.com)

---

## What It Does

- **Voice input** — speak naturally, no formatting required
- **AI structuring** — Claude processes your words into clean, organized entries with themes, emotions, and context
- **Timeline view** — your life, organized chronologically and searchable
- **Privacy-first** — your data stays yours
- **Export** — download your full memoir at any time

## Use Cases

- Daily journaling without the friction of typing
- Life documentation for people with memory or cognitive challenges
- Legacy writing — record stories for family
- Therapy homework — structured emotional processing

## Stack

```
Python · Flask · Claude (Anthropic) · Vanilla JS
Railway · Web Speech API
```

## Run Locally

```bash
pip install -r requirements.txt
cp .env.example .env  # add your Anthropic API key
python app.py
# → http://127.0.0.1:5568
```

---

*A Creative Konsoles project.*
