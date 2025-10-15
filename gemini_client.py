from google import genai
from google.genai import types
import os

class GeminiClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GENAI_API_KEY')
        if not self.api_key:
            raise RuntimeError('GENAI_API_KEY not set')
        self.client = genai.Client(api_key=self.api_key)

    def generate(self, prompt: str, system_instruction: str = None):
        cfg = types.GenerateContentConfig()
        if system_instruction:
            cfg.system_instruction = system_instruction
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            config=cfg,
            contents=prompt,
        )
        return response.text

    def create_chat(self, system_instruction: str = None):
        chat = self.client.chats.create(model="gemini-2.5-flash")
        if system_instruction:
            chat.send_message(system_instruction)
        return chat

    def send_message_stream(self, chat, message: str):
        # returns generator of chunks
        return chat.send_message_stream(message)
