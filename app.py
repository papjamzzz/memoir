"""
Memoir — Voice Memory Engine
Speak your story. We turn it into a memoir.
"""
import os, json, tempfile, glob
from flask import Flask, render_template, jsonify, request, Response
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
app = Flask(__name__)

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

VOICE_DIR       = 'voice'
CHAPTERS_DIR    = 'chapters'
CURRICULUM_PATH = 'data/curriculum.json'
SESSION_PATH    = 'sessions/lifepages_session.json'

# Ensure required dirs exist at startup (gunicorn doesn't run __main__)
for _d in [VOICE_DIR, CHAPTERS_DIR, 'sessions', 'output', 'data']:
    os.makedirs(_d, exist_ok=True)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    """Whisper STT — audio blob → text, saved to voice/"""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio'}), 400

    audio_file = request.files['audio']
    # Preserve real extension so Whisper handles MP3/MP4/WAV/M4A correctly
    original_name = audio_file.filename or 'audio.webm'
    ext = os.path.splitext(original_name)[1].lower() or '.webm'
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        with open(tmp_path, 'rb') as f:
            transcript = openai_client.audio.transcriptions.create(
                model='whisper-1',
                file=f,
                response_format='text'
            )
        text = transcript.strip()
        if text:
            _save_voice_entry(text)
        return jsonify({'text': text})
    except Exception as e:
        app.logger.error(f"Transcription failed: {e}")
        return jsonify({'error': 'transcription_failed'}), 500
    finally:
        os.unlink(tmp_path)


@app.route('/api/voice-log')
def voice_log():
    """Return all saved voice entries, newest first."""
    entries = _load_voice_entries()
    return jsonify(entries)


@app.route('/api/chapters')
def chapters():
    """Return list of memoir chapters."""
    files = sorted(glob.glob(f'{CHAPTERS_DIR}/*.txt'))
    result = []
    for f in files:
        name = os.path.basename(f).replace('.txt', '')
        try:
            with open(f) as fh:
                content = fh.read()
        except Exception:
            content = ''
        result.append({'name': name, 'content': content})
    return jsonify(result)


@app.route('/api/generate-chapter', methods=['POST'])
def generate_chapter():
    """Take all voice entries and generate a memoir chapter using Claude."""
    from anthropic import Anthropic

    entries = _load_voice_entries()
    if not entries:
        return jsonify({'error': 'No voice entries yet'}), 400

    # Build the voice transcript
    voice_text = '\n\n'.join([
        f"[{e['timestamp'][:10]}] {e['text']}"
        for e in entries[-20:]  # last 20 entries
    ])

    prompt = f"""You are a memoir writer helping someone capture their life story.
Below are raw voice recordings — spoken memories, unfiltered and real.

Your job: weave these into a warm, intimate memoir chapter.
Write in first person, as if the person is speaking directly to the reader.
Keep their voice. Don't over-polish. This should feel like a letter, not a book report.
Make it around 300-500 words. Give it a chapter title.

Raw voice entries:
{voice_text}

Write the chapter now:"""

    anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    message = anthropic_client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1000,
        messages=[{'role': 'user', 'content': prompt}]
    )

    chapter_text = message.content[0].text

    # Save as a .txt file in chapters/
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    chapter_name = f'chapter_{timestamp}'
    os.makedirs(CHAPTERS_DIR, exist_ok=True)
    path = f'{CHAPTERS_DIR}/{chapter_name}.txt'
    with open(path, 'w') as f:
        f.write(chapter_text)

    return jsonify({'chapter': chapter_text, 'name': chapter_name})


# ── Voice Interview Loop ──────────────────────────────────────────────────────

@app.route('/api/interview/start', methods=['POST'])
def interview_start():
    from anthropic import Anthropic
    data = request.get_json() or {}
    seed = data.get('seed', '').strip()

    seed_ctx = f'The person wants to explore this memory: "{seed}"' if seed else \
               'Ask them to name one specific memory — a moment, a place, a person. Be warm and specific.'

    prompt = f"""You are a memoir interviewer helping someone excavate a real memory from their life.
{seed_ctx}

Ask the opening question. Rules:
- One question only, no preamble
- Specific and warm, not generic
- Under 25 words
Just the question."""

    client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    msg = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=80,
        messages=[{'role': 'user', 'content': prompt}]
    )
    question = msg.content[0].text.strip()

    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    session = {
        'id': session_id,
        'created_at': datetime.now().isoformat(),
        'seed': seed,
        'exchanges': [{'question': question, 'answer': None, 'ts': datetime.now().isoformat()}]
    }
    os.makedirs('sessions', exist_ok=True)
    with open(f'sessions/interview_{session_id}.json', 'w') as f:
        json.dump(session, f, indent=2)

    return jsonify({'question': question, 'session_id': session_id})


@app.route('/api/interview/respond', methods=['POST'])
def interview_respond():
    from anthropic import Anthropic
    data = request.get_json() or {}
    session_id = data.get('session_id')
    answer = (data.get('answer') or '').strip()
    if not session_id or not answer:
        return jsonify({'error': 'missing fields'}), 400

    path = f'sessions/interview_{session_id}.json'
    try:
        with open(path) as f:
            session = json.load(f)
    except FileNotFoundError:
        return jsonify({'error': 'session not found'}), 404

    # Save answer to last open exchange
    for ex in reversed(session['exchanges']):
        if ex.get('answer') is None:
            ex['answer'] = answer
            ex['answered_at'] = datetime.now().isoformat()
            break
    else:
        session['exchanges'].append({'question': None, 'answer': answer, 'ts': datetime.now().isoformat()})

    answered = [e for e in session['exchanges'] if e.get('answer')]
    exchange_count = len(answered)

    if exchange_count >= 10:
        with open(path, 'w') as f:
            json.dump(session, f, indent=2)
        return jsonify({'done': True, 'exchange_count': exchange_count})

    # Build conversation history
    history = []
    for ex in session['exchanges']:
        if ex.get('question'): history.append(f"You asked: {ex['question']}")
        if ex.get('answer'):   history.append(f"They said: {ex['answer']}")
    convo = '\n'.join(history)

    prompt = f"""You are a memoir interviewer. Your job: ask one follow-up question that goes DEEPER into the memory.

Rules:
- One question only, no preamble
- Follow exactly what they just said — go specific, sensory, concrete
- Never ask "how did that make you feel?"
- Under 20 words

Conversation:
{convo}

Next question:"""

    client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    msg = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=60,
        messages=[{'role': 'user', 'content': prompt}]
    )
    next_q = msg.content[0].text.strip()

    session['exchanges'].append({'question': next_q, 'answer': None, 'ts': datetime.now().isoformat()})
    with open(path, 'w') as f:
        json.dump(session, f, indent=2)

    return jsonify({'question': next_q, 'done': False, 'exchange_count': exchange_count})


@app.route('/api/interview/generate', methods=['POST'])
def interview_generate():
    from anthropic import Anthropic
    data = request.get_json() or {}
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'missing session_id'}), 400

    path = f'sessions/interview_{session_id}.json'
    try:
        with open(path) as f:
            session = json.load(f)
    except FileNotFoundError:
        return jsonify({'error': 'session not found'}), 404

    pairs = [ex for ex in session['exchanges'] if ex.get('question') and ex.get('answer')]
    if not pairs:
        return jsonify({'error': 'no complete exchanges'}), 400

    transcript = '\n\n'.join(f"Q: {ex['question']}\nA: {ex['answer']}" for ex in pairs)

    prompt = f"""You are a skilled memoir writer. Below are raw interview exchanges — questions asked, answers spoken aloud by the person.

Write a full memoir chapter from this material.

Rules:
- First person, in their voice
- Use their exact words and phrases wherever possible — preserve their rhythm
- 1,500 to 2,500 words — a full chapter, not a sketch
- Give it a title on the first line
- Intimate and specific — feels like a letter to the future, not a book report
- Sensory detail throughout — light, smell, texture, sound
- No therapy-speak, no "this taught me that..." conclusions
- Let the memory breathe

Interview transcript:
{transcript}

Write the chapter:"""

    client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    msg = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=4000,
        messages=[{'role': 'user', 'content': prompt}]
    )
    chapter_text = msg.content[0].text.strip()

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f'chapter_{ts}'
    os.makedirs(CHAPTERS_DIR, exist_ok=True)
    with open(f'{CHAPTERS_DIR}/{name}.txt', 'w') as f:
        f.write(chapter_text)

    session['chapter'] = chapter_text
    session['chapter_generated_at'] = datetime.now().isoformat()
    with open(path, 'w') as f:
        json.dump(session, f, indent=2)

    return jsonify({'chapter': chapter_text, 'name': name, 'word_count': len(chapter_text.split())})


@app.route('/api/speak-prompt', methods=['POST'])
def speak_prompt():
    """ElevenLabs TTS — speak a prompt in Rachel's voice"""
    import requests as req
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        return jsonify({'error': 'no_key'}), 400

    data = request.get_json() or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'no_text'}), 400

    voice_id = 'hpp4J3VqNfWAUOO0d1Us'  # Bella — warm, bright (free tier)
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
    headers = {
        'xi-api-key': api_key,
        'Content-Type': 'application/json',
        'Accept': 'audio/mpeg'
    }
    payload = {
        'text': text,
        'model_id': 'eleven_turbo_v2_5',
        'voice_settings': {'stability': 0.82, 'similarity_boost': 0.75, 'speed': 0.78}
    }
    r = req.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        return jsonify({'error': 'elevenlabs_failed'}), 500

    return Response(r.content, mimetype='audio/mpeg')


# ── LifePages — Guided Curriculum ────────────────────────────────────────────

@app.route('/lifepages')
def lifepages():
    return render_template('lifepages.html')


@app.route('/api/lifepages/curriculum')
def lifepages_curriculum():
    """Return curriculum + session progress."""
    curriculum = _load_curriculum()
    session    = _load_lp_session()
    for chapter in curriculum['chapters']:
        cid     = chapter['id']
        cdata   = session.get(cid, {})
        answers = cdata.get('answers', {})
        chapter['status']    = cdata.get('status', 'not_started')
        chapter['generated'] = bool(cdata.get('generated_chapter'))
        chapter['answered']  = sum(
            1 for q in chapter['questions']
            if answers.get(q['id'], {}).get('answered')
        )
        chapter['total']  = len(chapter['questions'])
        chapter['ready']  = _is_ready(chapter['questions'], answers)
    return jsonify(curriculum)


@app.route('/api/lifepages/chapter/<chapter_id>')
def lifepages_chapter(chapter_id):
    """Return chapter questions + saved answers."""
    curriculum = _load_curriculum()
    chapter    = next((c for c in curriculum['chapters'] if c['id'] == chapter_id), None)
    if not chapter:
        return jsonify({'error': 'not_found'}), 404
    session = _load_lp_session()
    answers = session.get(chapter_id, {}).get('answers', {})
    for q in chapter['questions']:
        saved = answers.get(q['id'], {})
        q['answer']         = saved.get('text', '')
        q['sensitive_skip'] = saved.get('sensitive_skip', False)
        q['answered']       = saved.get('answered', False)
    chapter['status']          = session.get(chapter_id, {}).get('status', 'not_started')
    chapter['generated_chapter']= session.get(chapter_id, {}).get('generated_chapter', '')
    chapter['ready']           = _is_ready(chapter['questions'], answers)
    return jsonify(chapter)


@app.route('/api/lifepages/answer', methods=['POST'])
def lifepages_answer():
    """Save an answer to a question."""
    data       = request.get_json() or {}
    chapter_id = data.get('chapter_id')
    question_id= data.get('question_id')
    answer     = (data.get('answer') or '').strip()
    if not chapter_id or not question_id:
        return jsonify({'error': 'missing_fields'}), 400
    session = _load_lp_session()
    if chapter_id not in session:
        session[chapter_id] = {'status': 'in_progress', 'answers': {}}
    session[chapter_id]['status'] = 'in_progress'
    session[chapter_id]['answers'][question_id] = {
        'text':           answer,
        'answered':       bool(answer),
        'sensitive_skip': False,
        'saved_at':       datetime.now().isoformat()
    }
    _save_lp_session(session)
    return jsonify({'ok': True})


@app.route('/api/lifepages/skip', methods=['POST'])
def lifepages_skip():
    """Mark a question as a sensitive skip — counts as answered, never asked again."""
    data       = request.get_json() or {}
    chapter_id = data.get('chapter_id')
    question_id= data.get('question_id')
    if not chapter_id or not question_id:
        return jsonify({'error': 'missing_fields'}), 400
    session = _load_lp_session()
    if chapter_id not in session:
        session[chapter_id] = {'status': 'in_progress', 'answers': {}}
    session[chapter_id]['answers'][question_id] = {
        'text':           '',
        'answered':       True,
        'sensitive_skip': True,
        'saved_at':       datetime.now().isoformat()
    }
    _save_lp_session(session)
    return jsonify({'ok': True, 'message': "Totally understood — we'll leave that one out. Your story, your rules."})


@app.route('/api/lifepages/generate/<chapter_id>', methods=['POST'])
def lifepages_generate(chapter_id):
    """Generate a memoir chapter from collected answers."""
    from anthropic import Anthropic
    curriculum = _load_curriculum()
    chapter    = next((c for c in curriculum['chapters'] if c['id'] == chapter_id), None)
    if not chapter:
        return jsonify({'error': 'not_found'}), 404
    session = _load_lp_session()
    answers = session.get(chapter_id, {}).get('answers', {})
    if not _is_ready(chapter['questions'], answers):
        return jsonify({'error': 'not_ready', 'message': 'A few more questions needed before we can write this chapter.'}), 400

    # Build answered content, noting sensitive skips
    qa_lines = []
    skipped_topics = []
    for q in chapter['questions']:
        saved = answers.get(q['id'], {})
        if saved.get('sensitive_skip'):
            skipped_topics.append(q['text'])
        elif saved.get('answered') and saved.get('text'):
            qa_lines.append(f"Q: {q['text']}\nA: {saved['text']}")

    qa_block = '\n\n'.join(qa_lines)
    skip_note = ''
    if skipped_topics:
        skip_note = f"\n\nNote: The person preferred not to share details about these topics — omit them entirely:\n" + \
                    '\n'.join(f'- {t}' for t in skipped_topics)

    prompt = f"""You are a warm, skilled memoir writer helping someone capture their life story.

Chapter: {chapter['title']} — {chapter['subtitle']}
Context: {chapter['description']}

Below are the person's own words, gathered through guided questions. Your job is to weave these into a warm, intimate memoir chapter — written in first person, as if the person is speaking directly to the reader. Keep their voice. Don't over-polish. This should feel like a letter, not a book report. 300–500 words. Give it a title.

Their answers:
{qa_block}{skip_note}

Write the chapter now:"""

    client  = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1200,
        messages=[{'role': 'user', 'content': prompt}]
    )
    chapter_text = message.content[0].text

    # Save generated chapter
    if chapter_id not in session:
        session[chapter_id] = {'answers': {}}
    session[chapter_id]['status']           = 'complete'
    session[chapter_id]['generated_chapter']= chapter_text
    session[chapter_id]['generated_at']     = datetime.now().isoformat()
    _save_lp_session(session)

    return jsonify({'chapter': chapter_text, 'chapter_id': chapter_id})


@app.route('/api/lifepages/progress')
def lifepages_progress():
    """Overall completion stats."""
    curriculum = _load_curriculum()
    session    = _load_lp_session()
    total      = len(curriculum['chapters'])
    complete   = sum(1 for c in curriculum['chapters'] if session.get(c['id'], {}).get('status') == 'complete')
    in_progress= sum(1 for c in curriculum['chapters'] if session.get(c['id'], {}).get('status') == 'in_progress')
    return jsonify({'total': total, 'complete': complete, 'in_progress': in_progress})


# ── LifePages Helpers ─────────────────────────────────────────────────────────

def _load_curriculum():
    with open(CURRICULUM_PATH) as f:
        return json.load(f)


def _load_lp_session():
    try:
        with open(SESSION_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_lp_session(session):
    os.makedirs('sessions', exist_ok=True)
    with open(SESSION_PATH, 'w') as f:
        json.dump(session, f, indent=2)


def _is_ready(questions, answers):
    """Chapter is ready to generate when at least 1 of each type is answered + 4 total."""
    types_covered = set()
    total_answered = 0
    for q in questions:
        saved = answers.get(q['id'], {})
        if saved.get('answered'):
            types_covered.add(q['type'])
            total_answered += 1
    return len(types_covered) >= 3 and total_answered >= 4


@app.route('/api/reminder', methods=['POST'])
def reminder():
    """Store reminder preferences for future scheduling."""
    data = request.get_json() or {}
    interval_minutes = data.get('interval_minutes', 30)
    reminder_data = {
        'interval_minutes': interval_minutes,
        'created_at': datetime.now().isoformat()
    }
    with open('reminders.json', 'w') as f:
        json.dump(reminder_data, f, indent=2)
    return jsonify({'status': 'saved', 'interval_minutes': interval_minutes})


@app.route('/api/export', methods=['GET'])
def export_memoir():
    """Export all chapters as a single text file."""
    files = sorted(glob.glob(f'{CHAPTERS_DIR}/*.txt'))
    if not files:
        return jsonify({'error': 'No chapters yet'}), 400

    full_memoir = []
    for i, f in enumerate(files, 1):
        try:
            with open(f) as fh:
                content = fh.read()
            full_memoir.append(f"{'='*50}\n{content}\n")
        except Exception:
            pass

    combined = '\n\n'.join(full_memoir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    export_path = f'output/memoir_{timestamp}.txt'
    os.makedirs('output', exist_ok=True)
    with open(export_path, 'w') as f:
        f.write(combined)

    return Response(combined, mimetype='text/plain',
                   headers={'Content-Disposition': f'attachment; filename=memoir_{timestamp}.txt'})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_voice_entry(text):
    os.makedirs(VOICE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    entry = {
        'timestamp': datetime.now().isoformat(),
        'text': text,
    }
    path = f'{VOICE_DIR}/{timestamp}.json'
    with open(path, 'w') as f:
        json.dump(entry, f, indent=2)


def _load_voice_entries():
    files = sorted(glob.glob(f'{VOICE_DIR}/*.json'), reverse=True)
    entries = []
    for f in files:
        try:
            with open(f) as fh:
                entries.append(json.load(fh))
        except Exception:
            pass
    return entries


if __name__ == '__main__':
    os.makedirs(VOICE_DIR, exist_ok=True)
    os.makedirs(CHAPTERS_DIR, exist_ok=True)
    port = int(os.getenv('PORT', 5565))
    app.run(host='0.0.0.0', port=port, debug=False)
