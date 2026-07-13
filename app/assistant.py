import json
from pathlib import Path

from ollama import OllamaClient


class Assistant:

    def __init__(self):

        self.ai = OllamaClient()

        self.file = Path(__file__).resolve().parent.parent / "conv_history.json"

        self.load()

    def load(self):

        with open(self.file, "r") as f:
            self.state = json.load(f)

    def save(self):

        with open(self.file, "w") as f:
            json.dump(self.state, f, indent=4)

    def chat(self, prompt):

        self.history.append({

            "role": "user",

            "content": prompt

        })

        response = self.ai.chat(self.history)

        self.history.append({

            "role": "assistant",

            "content": response

        })

        self.save()

        return response

    @property
    def current_chat(self):

        return self.state["current_chat"]

    @property
    def history(self):

        return self.state["chats"][self.current_chat]