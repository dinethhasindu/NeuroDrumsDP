"""
NeuroDrums AI - Command pattern for Undo/Redo history.
"""
from __future__ import annotations
from typing import List

class Command:
    def execute(self):
        pass

    def undo(self):
        pass

class HistoryManager:
    def __init__(self, max_size=50):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self.max_size = max_size

    def push(self, command: Command):
        command.execute()
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self.max_size:
            self._undo_stack.pop(0)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        return True

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
