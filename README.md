# Healthcare Symptom Checker

Educational demo: input symptoms, get probable conditions and recommended next steps using Google Gemini via the `genai` Python client.

Warning: This project is for educational/demo purposes only. It is not medical advice.

Quick start

1. Create a virtual environment and install dependencies:

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create a `.env` file (see `.env.example`) and set `GENAI_API_KEY`.

3. Run the app:

```pwsh
python app.py
```

4. Open http://127.0.0.1:5000 in your browser.

Project layout

- `app.py` - Flask app and API endpoints
- `gemini_client.py` - thin wrapper around `genai` usage
- `models.py` - SQLAlchemy models for chats/messages
- `templates/` and `static/` - frontend UI
- `data.db` - SQLite DB (created at runtime)

Notes

- Use this app only for educational purposes. Always include a clear disclaimer when presenting health suggestions.
- Gemini API usage: costs may apply. Keep your API key safe.



video demo:
https://drive.google.com/file/d/1TpYEDmrFvPHc6tro1VZtJ_QwIh3424ga/view?usp=drivesdk
