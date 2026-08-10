from core.history import Command
from core.models import DrumEvent
import copy
import uuid


class MoveEventsCommand(Command):
    def __init__(self, project, ids, new_starts, old_starts, update_cb):
        self.project = project
        self.ids = ids
        self.new_starts = new_starts
        self.old_starts = old_starts
        self.update_cb = update_cb

    def execute(self):
        for eid, t in zip(self.ids, self.new_starts):
            for e in self.project.events:
                if e.id == eid:
                    e.start = t
                    e.end = t + e.duration
                    break
        self.update_cb()

    def undo(self):
        for eid, t in zip(self.ids, self.old_starts):
            for e in self.project.events:
                if e.id == eid:
                    e.start = t
                    e.end = t + e.duration
                    break
        self.update_cb()


class DeleteEventsCommand(Command):
    def __init__(self, project, ids, update_cb):
        self.project = project
        self.ids = ids
        self.update_cb = update_cb
        self.deleted_events = []

    def execute(self):
        self.deleted_events = [e for e in self.project.events if e.id in self.ids]
        self.project.events = [e for e in self.project.events if e.id not in self.ids]
        self.update_cb()

    def undo(self):
        self.project.events.extend(self.deleted_events)
        self.update_cb()


class DuplicateEventsCommand(Command):
    def __init__(self, project, ids, update_cb, offset: float = 0.125):
        self.project = project
        self.ids = ids
        self.update_cb = update_cb
        self.offset = offset
        self.new_events = []

    def execute(self):
        if not self.new_events:
            for e in self.project.events:
                if e.id in self.ids:
                    dup = copy.deepcopy(e)
                    dup.id = uuid.uuid4().hex[:8]
                    dup.start += self.offset
                    dup.end = dup.start + dup.duration
                    self.new_events.append(dup)
        self.project.events.extend(self.new_events)
        self.update_cb()

    def undo(self):
        new_ids = {e.id for e in self.new_events}
        self.project.events = [e for e in self.project.events if e.id not in new_ids]
        self.update_cb()


class PropertyChangeCommand(Command):
    def __init__(self, project, eid, attr, new_val, old_val, update_cb):
        self.project = project
        self.eid = eid
        self.attr = attr
        self.new_val = new_val
        self.old_val = old_val
        self.update_cb = update_cb

    def _apply(self, val):
        for e in self.project.events:
            if e.id == self.eid:
                setattr(e, self.attr, val)
                if self.attr == 'start':
                    e.end = e.start + e.duration
                elif self.attr == 'duration':
                    e.end = e.start + e.duration
                break
        self.update_cb()

    def execute(self):
        self._apply(self.new_val)

    def undo(self):
        self._apply(self.old_val)


class BulkModifyCommand(Command):
    def __init__(self, project, old_states, new_states, update_cb):
        self.project = project
        self.old_states = old_states
        self.new_states = new_states
        self.update_cb = update_cb

    def execute(self):
        for e in self.project.events:
            if e.id in self.new_states:
                for k, v in self.new_states[e.id].items():
                    setattr(e, k, v)
                if 'start' in self.new_states[e.id] or 'duration' in self.new_states[e.id]:
                    e.end = e.start + e.duration
        self.update_cb()

    def undo(self):
        for e in self.project.events:
            if e.id in self.old_states:
                for k, v in self.old_states[e.id].items():
                    setattr(e, k, v)
                if 'start' in self.old_states[e.id] or 'duration' in self.old_states[e.id]:
                    e.end = e.start + e.duration
        self.update_cb()


class AddEventsCommand(Command):
    def __init__(self, project, new_events, update_cb):
        self.project = project
        self.new_events = new_events
        self.update_cb = update_cb

    def execute(self):
        self.project.events.extend(self.new_events)
        self.update_cb()

    def undo(self):
        ids = {e.id for e in self.new_events}
        self.project.events = [e for e in self.project.events if e.id not in ids]
        self.update_cb()


class SplitEventsCommand(Command):
    def __init__(self, project, event_id, split_time, update_cb):
        self.project = project
        self.event_id = event_id
        self.split_time = split_time
        self.update_cb = update_cb
        self.left = None
        self.right = None
        self.original = None

    def execute(self):
        if self.left is not None:
            self.project.events.append(self.left)
            self.project.events.append(self.right)
            self.update_cb()
            return
        for i, e in enumerate(self.project.events):
            if e.id != self.event_id:
                continue
            if not (e.start < self.split_time < e.end):
                return
            self.original = copy.deepcopy(e)
            left_dur = self.split_time - e.start
            right_dur = e.end - self.split_time
            self.left = copy.deepcopy(e)
            self.left.id = uuid.uuid4().hex[:8]
            self.left.end = self.split_time
            self.left.duration = left_dur
            self.right = copy.deepcopy(e)
            self.right.id = uuid.uuid4().hex[:8]
            self.right.start = self.split_time
            self.right.duration = right_dur
            self.right.end = e.start + left_dur + right_dur
            self.right.source_offset_ms = e.source_offset_ms + left_dur * 1000.0
            self.project.events.pop(i)
            self.project.events.append(self.left)
            self.project.events.append(self.right)
            self.update_cb()
            return

    def undo(self):
        if self.left is None:
            return
        self.project.events = [e for e in self.project.events if e.id not in (self.left.id, self.right.id)]
        self.project.events.append(self.original)
        self.update_cb()


class PasteEventsCommand(Command):
    def __init__(self, project, clipboard, paste_time, lane, update_cb):
        self.project = project
        self.clipboard = clipboard
        self.paste_time = paste_time
        self.lane = lane
        self.update_cb = update_cb
        self.pasted = []

    def execute(self):
        if self.pasted:
            self.project.events.extend(self.pasted)
            self.update_cb()
            return
        if not self.clipboard:
            return
        min_start = min(e.start for e in self.clipboard)
        for src in self.clipboard:
            dup = copy.deepcopy(src)
            dup.id = uuid.uuid4().hex[:8]
            offset = src.start - min_start
            dup.start = self.paste_time + offset
            dup.end = dup.start + dup.duration
            if self.lane:
                dup.type = self.lane
            self.pasted.append(dup)
        self.project.events.extend(self.pasted)
        self.update_cb()

    def undo(self):
        ids = {e.id for e in self.pasted}
        self.project.events = [e for e in self.project.events if e.id not in ids]
        self.update_cb()


class ReplaceSampleCommand(Command):
    def __init__(self, project, event_ids, sample_path, old_paths, update_cb):
        self.project = project
        self.event_ids = event_ids
        self.sample_path = sample_path
        self.old_paths = old_paths
        self.update_cb = update_cb

    def execute(self):
        for e in self.project.events:
            if e.id in self.event_ids:
                e.replacement_sample = self.sample_path
                e.replace_mode = 'replace'
        self.update_cb()

    def undo(self):
        for e in self.project.events:
            if e.id in self.old_paths:
                e.replacement_sample = self.old_paths[e.id]
        self.update_cb()
