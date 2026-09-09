import sys

from .agent import handover


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(handover(target))


if __name__ == "__main__":
    main()
