import ast
import logging
import threading


class CallCounter(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls = 0

    def visit_Call(self, node: ast.Call) -> None:
        self.calls += 1
        self.generic_visit(node)


class Worker(threading.Thread):
    def run(self) -> None:
        print("working")


class ListHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        print(record)


def unused_control() -> str:
    return "never called"


def main() -> None:
    counter = CallCounter()
    counter.visit(ast.parse("f()"))
    Worker().start()
    logging.getLogger().addHandler(ListHandler())
