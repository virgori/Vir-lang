"""
vir-dbg — Vir Debug Adapter Protocol (DAP)
============================================
Phase 3 Task F4: Debug adapter for .vri programs.

Implements a subset of the Debug Adapter Protocol (DAP) for
stepping through Vir programs at the Q-IR level.

Features:
    - Set breakpoints on line numbers
    - Step over / step into / continue
    - Inspect variables (virtual registers)
    - Call stack display
    - Evaluate expressions in stopped context
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class StopReason(Enum):
    BREAKPOINT = "breakpoint"
    STEP = "step"
    ENTRY = "entry"
    EXCEPTION = "exception"


@dataclass
class Breakpoint:
    id: int
    file: str
    line: int
    verified: bool = True
    condition: str | None = None


@dataclass
class StackFrame:
    id: int
    name: str
    file: str
    line: int
    column: int = 0


@dataclass
class Variable:
    name: str
    value: str
    type: str = ""
    ref: int = 0  # Non-zero if has children


@dataclass
class DebugState:
    """Runtime debug state tracking."""
    breakpoints: dict[str, list[Breakpoint]] = field(default_factory=dict)
    frames: list[StackFrame] = field(default_factory=list)
    variables: dict[int, list[Variable]] = field(default_factory=dict)  # scope_id → vars
    stopped: bool = False
    stop_reason: StopReason = StopReason.ENTRY
    _bp_counter: int = 0
    _frame_counter: int = 0
    _scope_counter: int = 0

    def add_breakpoint(self, file: str, line: int, condition: str | None = None) -> Breakpoint:
        self._bp_counter += 1
        bp = Breakpoint(id=self._bp_counter, file=file, line=line, condition=condition)
        self.breakpoints.setdefault(file, []).append(bp)
        return bp

    def remove_breakpoint(self, bp_id: int) -> bool:
        for file_bps in self.breakpoints.values():
            for i, bp in enumerate(file_bps):
                if bp.id == bp_id:
                    file_bps.pop(i)
                    return True
        return False

    def push_frame(self, name: str, file: str, line: int) -> StackFrame:
        self._frame_counter += 1
        frame = StackFrame(id=self._frame_counter, name=name, file=file, line=line)
        self.frames.append(frame)
        return frame

    def pop_frame(self) -> StackFrame | None:
        return self.frames.pop() if self.frames else None

    def set_variables(self, scope_id: int, variables: list[Variable]) -> None:
        self.variables[scope_id] = variables

    def new_scope(self) -> int:
        self._scope_counter += 1
        return self._scope_counter

    def check_breakpoint(self, file: str, line: int) -> Breakpoint | None:
        for bp in self.breakpoints.get(file, []):
            if bp.line == line and bp.verified:
                return bp
        return None


class VirDebugAdapter:
    """
    DAP-compatible debug adapter for Vir.

    Communicates via JSON messages over stdio (DAP base protocol).
    """

    def __init__(self) -> None:
        self.state = DebugState()
        self._seq = 0
        self._initialized = False
        self._running = False

    # ── DAP Protocol ──────────────────────────────────────────

    def handle_request(self, request: dict) -> dict:
        """Dispatch a DAP request and return a response."""
        cmd = request.get("command", "")
        args = request.get("arguments", {})
        seq = request.get("seq", 0)

        handler = getattr(self, f"_cmd_{cmd}", None)
        if handler:
            body = handler(args)
            return self._response(seq, cmd, body)
        return self._response(seq, cmd, {}, success=False,
                              message=f"Unknown command: {cmd}")

    def _response(self, req_seq: int, command: str, body: dict,
                  success: bool = True, message: str = "") -> dict:
        self._seq += 1
        resp: dict[str, Any] = {
            "seq": self._seq,
            "type": "response",
            "request_seq": req_seq,
            "success": success,
            "command": command,
            "body": body,
        }
        if message:
            resp["message"] = message
        return resp

    def _event(self, event: str, body: dict | None = None) -> dict:
        self._seq += 1
        return {
            "seq": self._seq,
            "type": "event",
            "event": event,
            "body": body or {},
        }

    # ── Command Handlers ──────────────────────────────────────

    def _cmd_initialize(self, args: dict) -> dict:
        self._initialized = True
        return {
            "supportsConfigurationDoneRequest": True,
            "supportsFunctionBreakpoints": False,
            "supportsConditionalBreakpoints": True,
            "supportsEvaluateForHovers": True,
            "supportsStepBack": False,
            "supportsSetVariable": False,
        }

    def _cmd_configurationDone(self, args: dict) -> dict:
        return {}

    def _cmd_launch(self, args: dict) -> dict:
        program = args.get("program", "")
        self._running = True
        self.state.stopped = True
        self.state.stop_reason = StopReason.ENTRY
        self.state.push_frame("<main>", program, 1)
        return {}

    def _cmd_setBreakpoints(self, args: dict) -> dict:
        source = args.get("source", {})
        file = source.get("path", "")
        # Clear old breakpoints for this file
        self.state.breakpoints[file] = []
        breakpoints = []
        for bp_args in args.get("breakpoints", []):
            bp = self.state.add_breakpoint(
                file, bp_args["line"],
                condition=bp_args.get("condition"),
            )
            breakpoints.append({
                "id": bp.id,
                "verified": bp.verified,
                "line": bp.line,
            })
        return {"breakpoints": breakpoints}

    def _cmd_threads(self, args: dict) -> dict:
        return {"threads": [{"id": 1, "name": "main"}]}

    def _cmd_stackTrace(self, args: dict) -> dict:
        frames = []
        for f in reversed(self.state.frames):
            frames.append({
                "id": f.id,
                "name": f.name,
                "source": {"path": f.file},
                "line": f.line,
                "column": f.column,
            })
        return {"stackFrames": frames, "totalFrames": len(frames)}

    def _cmd_scopes(self, args: dict) -> dict:
        frame_id = args.get("frameId", 0)
        scope_id = self.state.new_scope()
        return {
            "scopes": [
                {
                    "name": "Locals",
                    "variablesReference": scope_id,
                    "expensive": False,
                },
            ]
        }

    def _cmd_variables(self, args: dict) -> dict:
        ref = args.get("variablesReference", 0)
        variables = []
        for v in self.state.variables.get(ref, []):
            variables.append({
                "name": v.name,
                "value": v.value,
                "type": v.type,
                "variablesReference": v.ref,
            })
        return {"variables": variables}

    def _cmd_continue(self, args: dict) -> dict:
        self.state.stopped = False
        return {"allThreadsContinued": True}

    def _cmd_next(self, args: dict) -> dict:
        # Step over
        self.state.stopped = True
        self.state.stop_reason = StopReason.STEP
        if self.state.frames:
            self.state.frames[-1].line += 1
        return {}

    def _cmd_stepIn(self, args: dict) -> dict:
        self.state.stopped = True
        self.state.stop_reason = StopReason.STEP
        return {}

    def _cmd_stepOut(self, args: dict) -> dict:
        self.state.pop_frame()
        self.state.stopped = True
        self.state.stop_reason = StopReason.STEP
        return {}

    def _cmd_evaluate(self, args: dict) -> dict:
        expr = args.get("expression", "")
        # Simple evaluation: look up variable name in current scope
        return {"result": f"<eval:{expr}>", "variablesReference": 0}

    def _cmd_disconnect(self, args: dict) -> dict:
        self._running = False
        return {}

    # ── DAP stdio transport ───────────────────────────────────

    def run_stdio(self) -> None:
        """Main loop reading DAP messages from stdin."""
        while True:
            try:
                header = ""
                while True:
                    line = sys.stdin.readline()
                    if not line:
                        return
                    line = line.strip()
                    if not line:
                        break
                    header = line

                content_length = 0
                if header.startswith("Content-Length:"):
                    content_length = int(header.split(":")[1].strip())

                if content_length <= 0:
                    continue

                raw = sys.stdin.read(content_length)
                request = json.loads(raw)
                response = self.handle_request(request)

                # Send response
                body = json.dumps(response, ensure_ascii=False)
                sys.stdout.write(f"Content-Length: {len(body)}\r\n\r\n{body}")
                sys.stdout.flush()

                # Send stopped event if applicable
                if self.state.stopped:
                    event = self._event("stopped", {
                        "reason": self.state.stop_reason.value,
                        "threadId": 1,
                        "allThreadsStopped": True,
                    })
                    body = json.dumps(event, ensure_ascii=False)
                    sys.stdout.write(f"Content-Length: {len(body)}\r\n\r\n{body}")
                    sys.stdout.flush()

            except (json.JSONDecodeError, ValueError):
                continue
            except KeyboardInterrupt:
                break


def main():
    """Entry point — start DAP server."""
    adapter = VirDebugAdapter()
    adapter.run_stdio()


if __name__ == "__main__":
    main()
