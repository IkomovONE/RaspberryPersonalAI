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

        self.ensure_defaults()

    def ensure_defaults(self):

        if "weather_broadcast" not in self.state:
            self.state["weather_broadcast"] = ""

        if "latest_news" not in self.state:
            self.state["latest_news"] = ""

        if "current_timestamp" not in self.state:
            self.state["current_timestamp"] = ""

        self.save()

    def save(self):

        with open(self.file, "w") as f:
            json.dump(self.state, f, indent=4)

    def new_chat(self, name):
        chat_id = name.lower()

        if chat_id in self.state["chats"]:

            return False

        # Initial system prompt for new chats: concise replies and chat name
        initial_system = (
            "You are a concise assistant. Reply in short, direct sentences. "
            "Default to brief answers unless the user explicitly asks for detail. "
            "Do not invent facts, especially for weather, news, dates, or time. "
            "Use only the latest authoritative values provided by the app in weather_broadcast, latest_news, and current_timestamp. "
            "When the user asks about weather, answer only from the weather_broadcast summary and current_timestamp. "
            "Do not add missing details such as wind direction, sunrise/sunset, or other inferred information unless they are explicitly present. "
            "If the prompt includes 'morning daily notification', treat it as a short daily weather summary and write one concise paragraph. "
            "When the user asks about news, answer only from latest_news and current_timestamp. "
            "If the needed data is not available, say 'I don't know' or 'I don't have current data'. "
            f"\n\nThis chat's name is: {name}"
        )

        self.state["chats"][chat_id] = {

            "name": name,

            "messages": [

                {"role": "system", "content": initial_system}

            ]

        }

        self.state["current_chat"] = chat_id

        self.save()

        return True
    
    def switch_chat(self, name):

        chat_id = name.lower()

        if chat_id not in self.state["chats"]:

            return False

        self.state["current_chat"] = chat_id

        self.save()

        return True

    def delete_chat(self, name):

        chat_id = name.lower()

        if chat_id not in self.state["chats"]:

            return False

        del self.state["chats"][chat_id]

        if self.state.get("current_chat") == chat_id:
            remaining_chats = list(self.state["chats"].keys())
            if remaining_chats:
                self.state["current_chat"] = remaining_chats[0]

        self.save()

        return True
    
    def list_chats(self):

        return [

            chat["name"]

            for chat in self.state["chats"].values()

        ]

    def update_global_value(self, key, value):

        self.state[key] = value
        self.save()

    def chat(self, prompt, save_to_history=True):

        history = list(self.history)
        history.append({

            "role": "user",

            "content": prompt

        })

        response = self.ai.chat(history)

        if save_to_history:
            self.history.append({

                "role": "user",

                "content": prompt

            })
            self.history.append({

                "role": "assistant",

                "content": response

            })
            self.save()

        return response
    
    def current_chat_name(self):

        return self.state["chats"][self.current_chat]["name"]

    @property
    def current_chat(self):

        return self.state["current_chat"]

    @property
    def history(self):

        return self.state["chats"][self.current_chat]["messages"]