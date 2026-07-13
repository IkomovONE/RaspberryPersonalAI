from ollama import OllamaClient
from telegram_bot import run


def main():

    ai = OllamaClient()

    print("Pi Assistant")
    print("Type 'exit' to quit.\n")

    while True:

        prompt = input("> ")

        if prompt.lower() == "exit":
            break

        answer = ai.ask(prompt)

        print()
        print(answer)
        print()


if __name__ == "__main__":
    run()