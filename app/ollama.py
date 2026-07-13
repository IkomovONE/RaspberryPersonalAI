import requests

from config import OLLAMA_URL, MODEL


class OllamaClient:

    def ask(self, prompt: str) -> str:

        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            }
        )

        response.raise_for_status()

        return response.json()["response"]