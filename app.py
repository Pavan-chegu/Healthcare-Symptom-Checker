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
            # Try to parse JSON from the model output
            import json

            try:
                # Some model outputs include markdown fences like ```json { ... } ```
                # Strip code fences and surrounding whitespace, then extract the first JSON object.
                cleaned = raw.strip()
                # Remove common markdown fences
                if cleaned.startswith('```') and cleaned.endswith('```'):
                    # remove the first and last fence lines
                    parts = cleaned.split('\n')
                    # drop the first line (```...)
                    if len(parts) >= 3:
                        cleaned = '\n'.join(parts[1:-1]).strip()

                # Try to find the first JSON object in the text using regex
                import re

                m = re.search(r"\{[\s\S]*\}", cleaned)
                if m:
                    json_text = m.group(0)
                else:
                    json_text = cleaned

                parsed = json.loads(json_text)
                # Build a compact, readable formatted text for the UI
                parts = []
                pcs = parsed.get('possible_conditions') or parsed.get('possibleConditions') or []
                if pcs:
                    parts.append('Possible conditions:')
                    for p in pcs:
                        name = p.get('name') if isinstance(p, dict) else str(p)
                        reason = p.get('reason') if isinstance(p, dict) else ''
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
            except Exception:
                # Parsing failed — fallback to raw trimmed text
                gen_response = raw.strip()
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
