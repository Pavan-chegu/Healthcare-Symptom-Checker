from typing import Any, Dict, List, Optional
from langchain.llms.base import LLM

from google import genai
from google.genai import types


class GeminiLLM(LLM):
    """A lightweight LangChain LLM wrapper for Google Gemini via google-genai.

    This implements the minimal interface LangChain expects: _call and
    _identifying_params.
    """

    model: str = "gemini-2.5-flash"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        if model:
            self.model = model
        self.api_key = api_key
        # client is lazily created
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            if self.api_key:
                self._client = genai.Client(api_key=self.api_key)
            else:
                self._client = genai.Client()
        return self._client

    @property
    def lc_secrets(self) -> Dict[str, str]:
        return {"api_key": self.api_key} if self.api_key else {}

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        client = self._get_client()
        cfg = types.GenerateContentConfig()
        if stop:
            cfg.stop = stop

        response = client.models.generate_content(
            model=self.model,
            config=cfg,
            contents=prompt,
        )
        return response.text

    def _identifying_params(self) -> Dict[str, Any]:
        return {"model": self.model}

    @property
    def _llm_type(self) -> str:  # pragma: no cover - small adapter
        return "gemini"
