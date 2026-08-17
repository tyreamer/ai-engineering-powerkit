import sys

from calculator import add


def main(argv: list[str]) -> int:
    operation, left, right = argv
    if operation != "add":
        raise ValueError(f"unsupported operation: {operation}")
    print(add(int(left), int(right)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
