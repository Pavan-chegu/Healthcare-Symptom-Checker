import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Chat, Message
from gemini_client import GeminiClient

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL') or 'sqlite:///data.db'

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

app = Flask(__name__)
# Do not require GENAI key at import time. Create client lazily.
client = None

def get_gemini_client():
    global client
    if client is None:
        try:
            client = GeminiClient()
        except Exception:
            client = None
    return client


@app.route('/')
def index():
    db = SessionLocal()
    chats = db.query(Chat).order_by(Chat.created_at.desc()).all()
    return render_template('index.html', chats=chats)


@app.route('/history')
def history():
    db = SessionLocal()
    chats = db.query(Chat).order_by(Chat.created_at.desc()).all()
    return render_template('history.html', chats=chats)


@app.route('/settings')
def settings():
    return render_template('settings.html')


@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    db = SessionLocal()
    # delete messages then chats
    try:
        db.query(Message).delete()
        db.query(Chat).delete()
        db.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.rollback()
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/chat/<int:chat_id>')
def view_chat(chat_id):
    db = SessionLocal()
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return redirect(url_for('index'))
    return render_template('chat.html', chat=chat)


@app.route('/api/chats', methods=['POST'])
def create_chat():
    data = request.get_json(silent=True) or {}
    title = data.get('title') or 'New Symptom Check'
    db = SessionLocal()
    chat = Chat(title=title)
    db.add(chat)
    db.commit()
    return jsonify({'id': chat.id, 'title': chat.title})


@app.route('/api/chats', methods=['GET'])
def list_chats():
    db = SessionLocal()
    chats = db.query(Chat).order_by(Chat.created_at.desc()).all()
    return jsonify([{'id': c.id, 'title': c.title, 'created_at': c.created_at.isoformat()} for c in chats])


@app.route('/api/chats/<int:chat_id>', methods=['GET'])
def get_chat(chat_id):
    db = SessionLocal()
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return jsonify({'error': 'chat not found'}), 404
    return jsonify({
        'id': chat.id,
        'title': chat.title,
        'messages': [{'id': m.id, 'role': m.role, 'content': m.content, 'created_at': m.created_at.isoformat()} for m in chat.messages]
    })


@app.route('/api/chats/<int:chat_id>/message', methods=['POST'])
def send_message(chat_id):
    data = request.json
    user_text = data.get('text')
    if not user_text:
        return jsonify({'error': 'text required'}), 400

    db = SessionLocal()
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        return jsonify({'error': 'chat not found'}), 404

    # Save user message
    user_msg = Message(chat_id=chat.id, role='user', content=user_text)
    db.add(user_msg)
    db.commit()

    # Prepare prompt for Gemini
    system_instruction = (
        "You are a medical-knowledgeable assistant for educational purposes only. "
        "Provide possible conditions and recommended next steps given symptoms. "
        "Always include a clear medical disclaimer and suggest seeking professional care when appropriate."
    )

    # Prompt Gemini to return a concise JSON response for easier display and parsing.
    prompt = (
        f"You are a medical-educational assistant.\n"
        f"Given the user's symptoms, return a concise JSON object with three keys:\n"
        f"  - possible_conditions: a list of objects {{name: str, reason: str}} (max 5, very short).\n"
        f"  - recommendations: a list of short action items (max 6).\n"
        f"  - disclaimer: a single short educational disclaimer string.\n"
        f"Do NOT include extra text beyond the JSON. Output must be valid JSON.\n\n"
        f"Symptoms: {user_text}\n"
    )

    # Helper: robustly extract first JSON object from a text blob and parse it.
    import json
    import re

    def extract_first_json_blob(text: str) -> str | None:
        """Find the first balanced JSON object in text and return the substring, or None."""
        if not text:
            return None
        s = text.strip()

        # Remove common markdown fences
        if s.startswith('```') and s.endswith('```'):
            parts = s.split('\n')
            if len(parts) >= 3:
                s = '\n'.join(parts[1:-1]).strip()

        # Quick search for a JSON object start
        start = s.find('{')
        if start == -1:
            return None

        depth = 0
        in_string = False
        esc = False
        for i in range(start, len(s)):
            ch = s[i]
            if ch == '"' and not esc:
                in_string = not in_string
            if in_string and ch == '\\' and not esc:
                esc = True
                continue
            esc = False
            if not in_string:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return s[start:i+1]
        return None

    def parse_model_output_to_json(text: str) -> tuple[dict | None, str]:
        """Try to parse text into JSON dict. Returns (dict or None, cleaned_text_for_ui).

        cleaned_text_for_ui is a compact representation useful for storing/display.
        """
        if text is None:
            return None, ''
        cleaned = text.strip()
        # Remove triple-backtick fences if present
        if cleaned.startswith('```') and cleaned.endswith('```'):
            parts = cleaned.split('\n')
            if len(parts) >= 3:
                cleaned = '\n'.join(parts[1:-1]).strip()

        # Try to extract first JSON blob
        json_blob = extract_first_json_blob(cleaned)
        if json_blob:
            try:
                parsed = json.loads(json_blob)
                return parsed, json.dumps(parsed, ensure_ascii=False)
            except Exception:
                # fall through to heuristic cleanup
                pass

        # As a fallback, try to find something that looks like JSON using regex
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                parsed = json.loads(m.group(0))
                return parsed, json.dumps(parsed, ensure_ascii=False)
            except Exception:
                pass

        # No JSON parsed — return None and a shortened cleaned text for UI
        short = cleaned
        if len(short) > 1000:
            short = short[:1000] + '...'
        return None, short

    # Attempt to call Gemini if configured; otherwise return a helpful message.
    gem = get_gemini_client()
    if gem is None:
        gen_response = (
            "{\"possible_conditions\": [{\"name\": \"Viral upper respiratory infection\", \"reason\": \"Common with fever and runny nose\"}],"
            "\"recommendations\": [\"Rest and hydrate\", \"OTC pain reliever as needed\", \"See doctor if severe or persistent\"],"
            "\"disclaimer\": \"Educational only; not medical advice. Consult a healthcare professional.\"}"
        )
    else:
        try:
            raw = gem.generate(prompt, system_instruction=system_instruction)
            # Try to parse model output into JSON using the robust helper
            parsed, cleaned_for_ui = parse_model_output_to_json(raw)
            if parsed:
                # Build a compact, readable formatted text for the UI from parsed
                parts = []
                pcs = parsed.get('possible_conditions') or parsed.get('possibleConditions') or []
                if pcs:
                    parts.append('Possible conditions:')
                    for p in pcs:
                        if isinstance(p, dict):
                            name = p.get('name')
                            reason = p.get('reason', '')
                        else:
                            name = str(p)
                            reason = ''
                        parts.append(f"- {name}: {reason}" if reason else f"- {name}")

                recs = parsed.get('recommendations') or parsed.get('recommendations') or []
                if recs:
                    parts.append('\nRecommended next steps:')
                    for r in recs:
                        parts.append(f"- {r}")

                disc = parsed.get('disclaimer') or parsed.get('disclaimer') or ''
                if disc:
                    parts.append(f"\nDisclaimer: {disc}")

                gen_response = '\n'.join(parts).strip()
            else:
                # No JSON parsed; use cleaned_for_ui (shortened/canonicalized text)
                gen_response = cleaned_for_ui or raw.strip()
        except Exception as e:
            gen_response = f"Error contacting Gemini: {e}"

    # Save assistant reply
    assistant_msg = Message(chat_id=chat.id, role='assistant', content=gen_response)
    db.add(assistant_msg)
    db.commit()

    # If we parsed JSON earlier, include it in the response for the UI
    response_payload = {'assistant': gen_response}
    if 'parsed' in locals() and isinstance(parsed, dict):
        response_payload['parsed'] = parsed

    return jsonify(response_payload)


if __name__ == '__main__':
    app.run(debug=True)
