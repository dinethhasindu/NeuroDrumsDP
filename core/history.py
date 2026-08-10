from typing import List, Callable, Any

class Command:
    def execute(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError

class HistoryManager:
    def __init__(self):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.on_changed: Callable[[], None] = lambda: None

    def execute(self, command: Command) -> None:
        command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self.on_changed()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self.on_changed()

    def redo(self) -> None:
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        command.execute()
        self.undo_stack.append(command)
        self.on_changed()

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.on_changed()
