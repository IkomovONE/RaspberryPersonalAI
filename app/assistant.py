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

    def new_chat(self, name):

        chat_id = name.lower()

        if chat_id in self.state["chats"]:

            return False

        self.state["chats"][chat_id] = {

            "name": name,

            "messages": []

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
    
    def current_chat_name(self):

        return self.state["chats"][self.current_chat]["name"]

    @property
    def current_chat(self):

        return self.state["current_chat"]

    @property
    def history(self):

        return self.state["chats"][self.current_chat]["messages"]