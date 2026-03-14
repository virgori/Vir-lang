"""
Virgex NFA Engine — Thompson NFA construction & simulation.

Builds a non-deterministic finite automaton from VPS AST nodes,
then runs Thompson's multi-state simulation for guaranteed O(n*m) matching
(no catastrophic backtracking).

This replaces the Python `re` backend when `engine='nfa'` is selected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .ast_nodes import (
    AtomNode,
    EscapedBlockNode,
    EscapedCharNode,
    GroupNode,
    LiteralNode,
    Node,
    OptionalNode,
    PatternNode,
    QuantifiedNode,
    SequenceNode,
    SpaceTokenNode,
)

# ═══════════════════════════════════════════════════════
# NFA State & Fragment
# ═══════════════════════════════════════════════════════

_state_counter = 0


def _new_id() -> int:
    global _state_counter
    _state_counter += 1
    return _state_counter


@dataclass
class NFAState:
    """A single NFA state with transitions."""
    id: int = field(default_factory=_new_id)
    # Character transitions: predicate → target state
    transitions: list[tuple[Callable[[str], bool] | None, NFAState]] = field(
        default_factory=list
    )
    # None predicate = ε-transition
    is_accept: bool = False


@dataclass
class Fragment:
    """An NFA fragment with one start state and a list of dangling arrows."""
    start: NFAState
    # Dangling arrows: list of (state, index) where transitions[index] has no target
    dangles: list[tuple[NFAState, int]]


def _patch(frag: Fragment, target: NFAState) -> None:
    """Connect all dangling arrows to a target state."""
    for state, idx in frag.dangles:
        pred, _ = state.transitions[idx]
        state.transitions[idx] = (pred, target)


def _frag_single(predicate: Callable[[str], bool] | None) -> Fragment:
    """Create a fragment that matches one character (or ε)."""
    s = NFAState()
    # Add transition with placeholder target (will be patched)
    s.transitions.append((predicate, s))  # temporary self-ref
    return Fragment(start=s, dangles=[(s, 0)])


# ═══════════════════════════════════════════════════════
# Atom → Character Predicate
# ═══════════════════════════════════════════════════════

def _atom_predicate(name: str) -> Callable[[str], bool]:
    """Convert a VPS atom name to a character predicate function."""
    if name == "Az":
        return lambda c: c.isalpha()
    if name == "AZ":
        return lambda c: c.isupper()
    if name == "az":
        return lambda c: c.islower()
    if name == "0":
        return lambda c: c.isdigit()
    if name == "Az0":
        return lambda c: c.isalnum()

    # Numeric range: e.g. "06" → '0'..'6'
    if len(name) == 2 and name[0].isdigit() and name[1].isdigit():
        lo, hi = name[0], name[1]
        return lambda c, _lo=lo, _hi=hi: _lo <= c <= _hi

    # Fallback: never matches
    return lambda c: False


# ═══════════════════════════════════════════════════════
# AST → NFA Construction (Thompson's)
# ═══════════════════════════════════════════════════════

def _build_node(node: Node) -> Fragment:
    """Recursively build an NFA fragment from an AST node."""

    if isinstance(node, PatternNode):
        return _build_node(node.body)

    if isinstance(node, SequenceNode):
        if not node.items:
            # Empty sequence = ε
            return _frag_single(None)
        frags = [_build_node(item) for item in node.items]
        # Concatenate: patch each frag's dangles to next frag's start
        result = frags[0]
        for i in range(1, len(frags)):
            _patch(result, frags[i].start)
            result = Fragment(start=result.start, dangles=frags[i].dangles)
        return result

    if isinstance(node, AtomNode):
        pred = _atom_predicate(node.name)
        return _frag_single(pred)

    if isinstance(node, LiteralNode):
        # Each character in the literal is a separate match
        frags = []
        for ch in node.value:
            def make_pred(c, _ch=ch):
                return c == _ch
            frags.append(_frag_single(make_pred))
        if not frags:
            return _frag_single(None)  # ε
        result = frags[0]
        for i in range(1, len(frags)):
            _patch(result, frags[i].start)
            result = Fragment(start=result.start, dangles=frags[i].dangles)
        return result

    if isinstance(node, EscapedCharNode):
        ch = node.char
        return _frag_single(lambda c, _ch=ch: c == _ch)

    if isinstance(node, EscapedBlockNode):
        # Match the entire block content literally
        frags = []
        for ch in node.content:
            def make_pred(c, _ch=ch):
                return c == _ch
            frags.append(_frag_single(make_pred))
        if not frags:
            return _frag_single(None)
        result = frags[0]
        for i in range(1, len(frags)):
            _patch(result, frags[i].start)
            result = Fragment(start=result.start, dangles=frags[i].dangles)
        return result

    if isinstance(node, SpaceTokenNode):
        return _frag_single(lambda c: c == ' ')

    if isinstance(node, QuantifiedNode):
        return _build_quantified(node)

    if isinstance(node, OptionalNode):
        # Optional = 0 or 1 repetition
        inner = _build_node(node.expression)
        # Create a split state: ε→inner or ε→bypass
        split = NFAState()
        split.transitions.append((None, inner.start))  # go to inner
        split.transitions.append((None, split))         # bypass (dangling)
        # Dangles: inner's dangles + the bypass arrow
        dangles = inner.dangles + [(split, 1)]
        return Fragment(start=split, dangles=dangles)

    if isinstance(node, GroupNode):
        if not node.alternatives:
            return _frag_single(None)
        if len(node.alternatives) == 1:
            return _build_node(node.alternatives[0])
        # Alternation: split state with ε-transitions to each alternative
        split = NFAState()
        all_dangles: list[tuple[NFAState, int]] = []
        for i, alt in enumerate(node.alternatives):
            alt_frag = _build_node(alt)
            idx = len(split.transitions)
            split.transitions.append((None, alt_frag.start))
            all_dangles.extend(alt_frag.dangles)
        return Fragment(start=split, dangles=all_dangles)

    # Unknown node type — treat as ε
    return _frag_single(None)


def _build_quantified(node: QuantifiedNode) -> Fragment:
    """Build NFA for quantified expressions: !n, !n~m, !n~, etc."""
    qmin = node.min
    qmax = node.max  # None = unbounded

    # First: concatenate qmin required copies
    required_frags = []
    for _ in range(qmin):
        required_frags.append(_build_node(node.expression))

    if qmin == 0 and qmax is None:
        # Kleene star: 0 or more
        inner = _build_node(node.expression)
        split = NFAState()
        split.transitions.append((None, inner.start))  # enter loop
        split.transitions.append((None, split))         # bypass (dangle)
        _patch(inner, split)  # loop back
        return Fragment(start=split, dangles=[(split, 1)])

    if qmin >= 1 and qmax is None:
        # 1+ or n+: required copies then Kleene star
        result = required_frags[0]
        for i in range(1, len(required_frags)):
            _patch(result, required_frags[i].start)
            result = Fragment(start=result.start, dangles=required_frags[i].dangles)
        # Append a Kleene star
        inner = _build_node(node.expression)
        split = NFAState()
        split.transitions.append((None, inner.start))
        split.transitions.append((None, split))  # bypass
        _patch(inner, split)
        _patch(result, split)
        return Fragment(start=result.start, dangles=[(split, 1)])

    if qmax is not None:
        # Bounded: qmin..qmax
        # Required copies
        if required_frags:
            result = required_frags[0]
            for i in range(1, len(required_frags)):
                _patch(result, required_frags[i].start)
                result = Fragment(start=result.start, dangles=required_frags[i].dangles)
        else:
            result = None

        # Optional copies for (qmax - qmin) times
        extra_dangles: list[tuple[NFAState, int]] = []
        for _ in range(qmax - qmin):
            opt_inner = _build_node(node.expression)
            split = NFAState()
            split.transitions.append((None, opt_inner.start))
            split.transitions.append((None, split))  # bypass
            extra_dangles.append((split, 1))

            if result is not None:
                _patch(result, split)
                result = Fragment(start=result.start, dangles=opt_inner.dangles)
            else:
                result = Fragment(start=split, dangles=opt_inner.dangles)

        if result is not None:
            return Fragment(start=result.start,
                          dangles=result.dangles + extra_dangles)
        return _frag_single(None)

    # Fallback
    return _frag_single(None)


# ═══════════════════════════════════════════════════════
# NFA Compilation
# ═══════════════════════════════════════════════════════

@dataclass
class CompiledNFA:
    """A compiled NFA ready for matching."""
    start: NFAState
    accept: NFAState
    anchor_start: bool
    anchor_end: bool


def compile_nfa(ast: PatternNode) -> CompiledNFA:
    """Compile a VPS AST into an NFA."""
    global _state_counter
    _state_counter = 0

    frag = _build_node(ast.body)
    accept = NFAState(is_accept=True)
    _patch(frag, accept)

    return CompiledNFA(
        start=frag.start,
        accept=accept,
        anchor_start=ast.anchor_start,
        anchor_end=ast.anchor_end,
    )


# ═══════════════════════════════════════════════════════
# Thompson NFA Simulation
# ═══════════════════════════════════════════════════════

def _epsilon_closure(states: set[int], state_map: dict[int, NFAState]) -> set[int]:
    """Compute ε-closure of a set of states."""
    stack = list(states)
    closure = set(states)
    while stack:
        sid = stack.pop()
        state = state_map[sid]
        for pred, target in state.transitions:
            if pred is None and target.id not in closure:
                closure.add(target.id)
                stack.append(target.id)
    return closure


def _collect_states(start: NFAState) -> dict[int, NFAState]:
    """Collect all reachable states from start into a dict."""
    visited: dict[int, NFAState] = {}
    stack = [start]
    while stack:
        s = stack.pop()
        if s.id in visited:
            continue
        visited[s.id] = s
        for _, target in s.transitions:
            if target.id not in visited:
                stack.append(target)
    return visited


def nfa_fullmatch(nfa: CompiledNFA, text: str) -> bool:
    """Test if the entire text matches the NFA."""
    state_map = _collect_states(nfa.start)
    current = _epsilon_closure({nfa.start.id}, state_map)

    for ch in text:
        next_states: set[int] = set()
        for sid in current:
            state = state_map[sid]
            for pred, target in state.transitions:
                if pred is not None and pred(ch):
                    next_states.add(target.id)
        current = _epsilon_closure(next_states, state_map)
        if not current:
            return False

    return nfa.accept.id in current


def nfa_search(nfa: CompiledNFA, text: str) -> tuple[int, int] | None:
    """
    Find the first (leftmost-longest) match in text.
    Returns (start, end) or None.
    """
    state_map = _collect_states(nfa.start)

    if nfa.anchor_start:
        # Must match from position 0
        start_positions = [0]
    else:
        start_positions = range(len(text) + 1)

    for start_pos in start_positions:
        current = _epsilon_closure({nfa.start.id}, state_map)
        last_match: int | None = None

        if nfa.accept.id in current:
            last_match = start_pos

        for i in range(start_pos, len(text)):
            ch = text[i]
            next_states: set[int] = set()
            for sid in current:
                state = state_map[sid]
                for pred, target in state.transitions:
                    if pred is not None and pred(ch):
                        next_states.add(target.id)

            current = _epsilon_closure(next_states, state_map)
            if not current:
                break

            if nfa.accept.id in current:
                last_match = i + 1

        if last_match is not None:
            if nfa.anchor_end and last_match != len(text):
                continue
            return (start_pos, last_match)

    return None


def nfa_findall(nfa: CompiledNFA, text: str) -> list[tuple[int, int]]:
    """Find all non-overlapping matches."""
    state_map = _collect_states(nfa.start)
    results: list[tuple[int, int]] = []
    pos = 0

    while pos <= len(text):
        current = _epsilon_closure({nfa.start.id}, state_map)
        last_match: int | None = None

        if nfa.accept.id in current:
            last_match = pos

        for i in range(pos, len(text)):
            ch = text[i]
            next_states: set[int] = set()
            for sid in current:
                state = state_map[sid]
                for pred, target in state.transitions:
                    if pred is not None and pred(ch):
                        next_states.add(target.id)

            current = _epsilon_closure(next_states, state_map)
            if not current:
                break

            if nfa.accept.id in current:
                last_match = i + 1

        if last_match is not None:
            results.append((pos, last_match))
            pos = last_match if last_match > pos else pos + 1
        else:
            pos += 1

    return results
