def format_row(cells: list[str]) -> str:
    return " | ".join(cells)


def strip_rows(rows: list[str]) -> list[str]:
    return [row.strip() for row in rows]


def print_usage() -> None:
    print("usage: python -m _maintenance")


def debug_dump(rows: list[str]) -> None:
    print(rows)


def unused_control() -> None:
    pass
