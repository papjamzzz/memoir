# memoir — Re-Entry File

## What This Is
A voice-to-code memoir. Jeremiah speaks memories into the Voice Studio.
Raw transcripts save to `voice/`. Claude weaves them into code chapters in `chapters/`.
The code IS the memoir — it runs and tells the story.

## Re-Entry Phrase
"Re-entry: memoir"

## Port
5565

## Stack
- Flask, port 5565
- OpenAI Whisper-1 (STT)
- Dark warm writing-desk UI (Lora + JetBrains Mono)

## How It Works
1. User opens http://127.0.0.1:5565
2. Taps mic, speaks a memory
3. Whisper transcribes → saved to voice/TIMESTAMP.json
4. In Claude Code sessions: read voice/ entries → weave into chapters/*.py
5. Chapters render in the right panel

## Code-as-Memoir Language
| Code construct | Narrative meaning |
|----------------|------------------|
| class          | A phase of life, an identity |
| def            | A moment, an event, a memory |
| if/else        | A crossroads, a decision |
| try/except     | When things broke — and survival |
| while          | Patterns, cycles |
| break          | The moment of escape |
| return         | What you carried forward |
| import         | Who shaped you |
| # comment      | The inner voice |
| """docstring""" | The prose, the full narrative |
| None           | Absence. Loss. |
| assert         | What you believed to be true |
| del            | What you let go |
| yield          | What you gave |
| pass           | When you had nothing left to say |
| raise          | When you stood up |

## Story Timeline
*(Claude fills this in as chapters are written)*

## Voice Log Summary
*(Claude summarizes raw entries as they accumulate)*

## File Structure
```
memoir/
├── CLAUDE.md
├── app.py
├── templates/index.html
├── chapters/          ← the book, in code
├── voice/             ← raw spoken memories (JSON)
└── output/            ← rendered memoir (future)
```

---
*Started: 2026-04-04*
