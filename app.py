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

VOICE_DIR    = 'voice'
CHAPTERS_DIR = 'chapters'


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
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
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
    app.run(host='127.0.0.1', port=5563, debug=False)
