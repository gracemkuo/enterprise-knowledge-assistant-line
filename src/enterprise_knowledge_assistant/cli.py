import argparse

from .config import get_settings
from .knowledge import AgentSearchClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test Agent Search before connecting a messaging channel."
    )
    parser.add_argument("question")
    args = parser.parse_args()

    settings = get_settings()
    answer = AgentSearchClient(settings).ask(args.question, "local-poc-user")
    print(answer.text)
    for index, source in enumerate(answer.sources, start=1):
        print(f"\n{index}. {source.title}\n{source.uri}")


if __name__ == "__main__":
    main()
