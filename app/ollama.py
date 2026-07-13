import requests

from config import OLLAMA_URL, MODEL


class OllamaClient:

    def chat(self, messages):

        response = requests.post(

            f"{OLLAMA_URL}/api/chat",

            json={

                "model": MODEL,

                "messages": messages,

                "stream": False

            }

        )

        response.raise_for_status()

        return response.json()["message"]["content"]