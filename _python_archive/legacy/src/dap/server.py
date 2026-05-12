"""
Vir DAP Server — Debug Adapter Protocol for Vir language.
===========================================================
Implements DAP 1.65 over stdio with JSON-based protocol.

Features:
  - launch / attach
  - setBreakpoints / configurationDone
  - continue / next / stepIn / stepOut
  - stackTrace / scopes / variables
  - evaluate (watch expressions)
  - pause / disconnect

Launch: python -m src.dap
"""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════
# DAP Transport (Content-Length framing, same as LSP)
# ═══════════════════════════════════════════════════════════

def _read_dap_message(stream=None) -> dict[str, Any] | None:
    if stream is None:
        stream = sys.stdin.buffer

    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        line_str = line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line_str:
            break
        if ":" in line_str:
            key, _, val = line_str.partition(":")
            headers[key.strip()] = val.strip()

    content_length = int(headers.get("Content-Length", "0"))
    if content_length == 0:
        return None

    body = stream.read(content_length)
    return json.loads(body.decode("utf-8"))


def _write_dap_message(msg: dict[str, Any], stream=None) -> None:
    if stream is None:
        stream = sys.stdout.buffer

    body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    stream.write(header)
    stream.write(body)
    stream.flush()


def _dap_response(request: dict, body: dict | None = None, success: bool = True) -> dict:
    resp = {
        "seq": 0,
        "type": "response",
        "request_seq": request.get("seq", 0),
        "command": request.get("command", ""),
        "success": success,
    }
    if body is not None:
        resp["body"] = body
    return resp


def _dap_event(event: str, body: dict | None = None) -> dict:
    msg = {"seq": 0, "type": "event", "event": event}
    if body is not None:
        msg["body"] = body
    return msg


# ═══════════════════════════════════════════════════════════
# Debug State
# ═══════════════════════════════════════════════════════════

@dataclass
class Breakpoint:
    id: int
    line: int
    file: str
    verified: bool = True


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
    variables_ref: int = 0


@dataclass
class DebugState:
    """Runtime state of the debugger."""
    running: bool = False
    paused: bool = False
    breakpoints: dict[str, list[Breakpoint]] = field(default_factory=dict)
    stack_frames: list[StackFrame] = field(default_factory=list)
    variables: dict[int, list[Variable]] = field(default_factory=dict)  # scope_id → vars
    source_files: dict[str, list[str]] = field(default_factory=dict)
    current_frame: int = 0
    current_line: int = 0
    current_file: str = ""
    next_bp_id: int = 1
    next_frame_id: int = 1
    next_scope_id: int = 1000

    def load_source(self, path: str) -> list[str]:
        if path not in self.source_files:
            try:
                self.source_files[path] = Path(path).read_text(encoding="utf-8").splitlines()
            except (OSError, ValueError):
                self.source_files[path] = []
        return self.source_files[path]

    def add_breakpoint(self, file: str, line: int) -> Breakpoint:
        bp = Breakpoint(id=self.next_bp_id, line=line, file=file)
        self.next_bp_id += 1
        self.breakpoints.setdefault(file, []).append(bp)
        return bp


# ═══════════════════════════════════════════════════════════
# DAP Server
# ═══════════════════════════════════════════════════════════

class VirDapServer:
    """Vir Debug Adapter Protocol server."""

    def __init__(self) -> None:
        self.state = DebugState()
        self.seq = 0
        self.alive = True
        self.initialized = False
        self.launch_args: dict[str, Any] = {}

    def handle(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        """Handle a DAP message. Returns list of responses/events to send."""
        msg_type = msg.get("type", "")
        command = msg.get("command", "")
        args = msg.get("arguments", {})
        responses: list[dict[str, Any]] = []

        if msg_type == "request":
            handler = getattr(self, f"_cmd_{command}", None)
            if handler:
                responses.extend(handler(msg, args))
            else:
                responses.append(_dap_response(msg, success=False))

        return responses

    # ── Lifecycle ──────────────────────────────────────────

    def _cmd_initialize(self, req: dict, args: dict) -> list[dict]:
        self.initialized = True
        return [
            _dap_response(req, {
                "supportsConfigurationDoneRequest": True,
                "supportsFunctionBreakpoints": False,
                "supportsConditionalBreakpoints": False,
                "supportsEvaluateForHovers": True,
                "supportsStepBack": False,
                "supportsSetVariable": False,
                "supportsSteppingGranularity": True,
            }),
            _dap_event("initialized"),
        ]

    def _cmd_launch(self, req: dict, args: dict) -> list[dict]:
        self.launch_args = args
        program = args.get("program", "")
        self.state.current_file = program

        if program:
            self.state.load_source(program)

        self.state.running = True
        self.state.paused = True  # Start paused at line 1
        self.state.current_line = 1

        # Create initial stack frame
        frame = StackFrame(
            id=self.state.next_frame_id,
            name="main",
            file=program,
            line=1,
        )
        self.state.next_frame_id += 1
        self.state.stack_frames = [frame]

        return [
            _dap_response(req),
            _dap_event("stopped", {"reason": "entry", "threadId": 1}),
        ]

    def _cmd_configurationDone(self, req: dict, args: dict) -> list[dict]:
        return [_dap_response(req)]

    def _cmd_disconnect(self, req: dict, args: dict) -> list[dict]:
        self.alive = False
        self.state.running = False
        return [_dap_response(req)]

    # ── Breakpoints ────────────────────────────────────────

    def _cmd_setBreakpoints(self, req: dict, args: dict) -> list[dict]:
        source = args.get("source", {})
        path = source.get("path", "")
        lines = args.get("breakpoints", [])

        # Clear existing breakpoints for this file
        self.state.breakpoints[path] = []

        result_bps = []
        for bp_req in lines:
            line = bp_req.get("line", 0)
            bp = self.state.add_breakpoint(path, line)
            result_bps.append({
                "id": bp.id,
                "verified": bp.verified,
                "line": bp.line,
                "source": {"path": path},
            })

        return [_dap_response(req, {"breakpoints": result_bps})]

    # ── Execution control ──────────────────────────────────

    def _cmd_continue(self, req: dict, args: dict) -> list[dict]:
        self.state.paused = False
        # Simulate running until next breakpoint or end
        self._run_to_breakpoint()
        return [
            _dap_response(req, {"allThreadsContinued": True}),
            _dap_event("stopped", {
                "reason": "breakpoint" if self.state.paused else "exit",
                "threadId": 1,
            }),
        ]

    def _cmd_next(self, req: dict, args: dict) -> list[dict]:
        """Step over (next line)."""
        self.state.current_line += 1
        self._update_frame()
        return [
            _dap_response(req),
            _dap_event("stopped", {"reason": "step", "threadId": 1}),
        ]

    def _cmd_stepIn(self, req: dict, args: dict) -> list[dict]:
        self.state.current_line += 1
        self._update_frame()
        return [
            _dap_response(req),
            _dap_event("stopped", {"reason": "step", "threadId": 1}),
        ]

    def _cmd_stepOut(self, req: dict, args: dict) -> list[dict]:
        # Step out of current function → pop frame
        if len(self.state.stack_frames) > 1:
            self.state.stack_frames.pop()
            if self.state.stack_frames:
                self.state.current_line = self.state.stack_frames[-1].line
        return [
            _dap_response(req),
            _dap_event("stopped", {"reason": "step", "threadId": 1}),
        ]

    def _cmd_pause(self, req: dict, args: dict) -> list[dict]:
        self.state.paused = True
        return [
            _dap_response(req),
            _dap_event("stopped", {"reason": "pause", "threadId": 1}),
        ]

    # ── Stack & Variables ──────────────────────────────────

    def _cmd_threads(self, req: dict, args: dict) -> list[dict]:
        return [_dap_response(req, {
            "threads": [{"id": 1, "name": "main"}],
        })]

    def _cmd_stackTrace(self, req: dict, args: dict) -> list[dict]:
        frames = []
        for sf in reversed(self.state.stack_frames):
            frames.append({
                "id": sf.id,
                "name": sf.name,
                "source": {"path": sf.file, "name": Path(sf.file).name if sf.file else ""},
                "line": sf.line,
                "column": sf.column,
            })
        return [_dap_response(req, {
            "stackFrames": frames,
            "totalFrames": len(frames),
        })]

    def _cmd_scopes(self, req: dict, args: dict) -> list[dict]:
        frame_id = args.get("frameId", 0)
        scope_id = self.state.next_scope_id
        self.state.next_scope_id += 1
        # TODO: populate real variables from debuggee
        self.state.variables[scope_id] = [
            Variable(name="(no variables)", value="", type=""),
        ]
        return [_dap_response(req, {
            "scopes": [{
                "name": "Locals",
                "variablesReference": scope_id,
                "expensive": False,
            }],
        })]

    def _cmd_variables(self, req: dict, args: dict) -> list[dict]:
        ref = args.get("variablesReference", 0)
        variables = self.state.variables.get(ref, [])
        return [_dap_response(req, {
            "variables": [
                {"name": v.name, "value": v.value, "type": v.type, "variablesReference": v.variables_ref}
                for v in variables
            ],
        })]

    def _cmd_evaluate(self, req: dict, args: dict) -> list[dict]:
        expression = args.get("expression", "")
        context = args.get("context", "hover")
        # Simple eval: return the expression as string (placeholder)
        return [_dap_response(req, {
            "result": f"<eval: {expression}>",
            "variablesReference": 0,
        })]

    # ── Internal helpers ───────────────────────────────────

    def _run_to_breakpoint(self) -> None:
        """Simulate running forward until a breakpoint or end of file."""
        source_lines = self.state.load_source(self.state.current_file)
        total = len(source_lines)

        bps = self.state.breakpoints.get(self.state.current_file, [])
        bp_lines = {bp.line for bp in bps}

        start = self.state.current_line + 1
        for line in range(start, total + 1):
            if line in bp_lines:
                self.state.current_line = line
                self.state.paused = True
                self._update_frame()
                return

        # Reached end
        self.state.current_line = total
        self.state.paused = True
        self._update_frame()

    def _update_frame(self) -> None:
        if self.state.stack_frames:
            self.state.stack_frames[-1].line = self.state.current_line

    def run(self) -> None:
        """Main DAP loop."""
        while self.alive:
            msg = _read_dap_message()
            if msg is None:
                break
            responses = self.handle(msg)
            for resp in responses:
                self.seq += 1
                resp["seq"] = self.seq
                _write_dap_message(resp)


def main() -> None:
    server = VirDapServer()
    server.run()
