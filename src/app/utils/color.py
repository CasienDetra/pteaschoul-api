"""Colored terminal output for the seeder CLI."""

RESET = "\033[0m"
BOLD = "\033[1m"
_CODES = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "cyan": "\033[36m",
    "grey": "\033[90m",
}


def paint(text: str, color: str, bold: bool = False) -> str:
    return f"{BOLD if bold else ''}{_CODES.get(color, '')}{text}{RESET}"


def info(text: str) -> None:
    print(paint(f"→ {text}", "cyan"))


def ok(text: str) -> None:
    print(paint(f"✓ {text}", "green"))


def warn(text: str) -> None:
    print(paint(f"! {text}", "yellow"))


def error(text: str) -> None:
    print(paint(f"✗ {text}", "red"))


def title(text: str) -> None:
    print(paint(f"\n{text}", "blue", bold=True))
