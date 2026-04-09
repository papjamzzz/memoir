"""
Memoir — Voice-to-Code Writing Engine
Speak your story. We turn it into code.
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
    """Return list of code chapters."""
    files = sorted(glob.glob(f'{CHAPTERS_DIR}/*.py'))
    result = []
    for f in files:
        name = os.path.basename(f).replace('.py', '')
        try:
            with open(f) as fh:
                content = fh.read()
        except Exception:
            content = ''
        result.append({'name': name, 'content': content})
    return jsonify(result)


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
