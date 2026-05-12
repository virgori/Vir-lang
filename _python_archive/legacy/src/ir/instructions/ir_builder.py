"""
ir_builder.py – AST → Q-IR lowering
=====================================
Dịch cây AST (từ Parser) thành các QInstruction trong QModule.
"""

from __future__ import annotations

from src.frontend.parser.parser import (
    AccessNode,
    ASTNode,
    AssignNode,
    BinOpNode,
    BreakNode,
    CallNode,
    CheckCPUNode,
    CompareNode,
    ContinueNode,
    EntityDefNode,
    EntityNode,
    ForNode,
    FuncDefNode,
    IdentifierRef,
    IfNode,
    InputNode,
    LogicOpNode,
    LoopNode,
    MapNode,
    NumberLiteral,
    PatchPointNode,
    PrintNode,
    ProgramNode,
    ReturnNode,
    StringLiteral,
    TryErrorNode,
    VarDeclNode,
    WhileNode,
)
from src.ir.instructions.q_ir import (
    Immediate,
    Label,
    Opcode,
    QFunction,
    QInstruction,
    QModule,
    VReg,
)
from src.ir.registers.virtual_registers import VirtualRegisterAllocator


class IRBuilder:
    """Dịch ProgramNode → QModule."""

    def __init__(self) -> None:
        self.module = QModule()
        self._alloc = VirtualRegisterAllocator()
        self._current_func: QFunction | None = None
        self._label_counter = 0
        self._patch_counter = 0
        self._loop_stack: list[tuple[Label, Label]] = []  # (continue_label, break_label)
        self._types: dict[str, str] = {}  # vreg_name -> type_name

    # ── Helpers ────────────────────────────────────────────
    def _new_label(self, prefix: str = "L") -> Label:
        self._label_counter += 1
        return Label(f"{prefix}_{self._label_counter}")

    def _new_patch_id(self) -> str:
        self._patch_counter += 1
        return f"PATCH_{self._patch_counter}"

    def _emit(self, instr: QInstruction) -> None:
        if self._current_func:
            self._current_func.append(instr)

    def _ensure_func(self) -> None:
        """Đảm bảo có function context (tạo implicit main nếu cần)."""
        if self._current_func is None:
            main = QFunction(name="__main__")
            self.module.add_function(main)
            self._current_func = main

    # ── Public entry point ─────────────────────────────────
    def build(self, program: ProgramNode) -> QModule:
        """Dịch ProgramNode thành QModule."""
        for stmt in program.statements:
            self._lower_statement(stmt)
        return self.module

    # ── Statement lowering ─────────────────────────────────
    def _lower_statement(self, node: ASTNode) -> None:
        match node:
            case FuncDefNode():
                self._lower_func_def(node)
            case VarDeclNode():
                self._lower_var_decl(node)
            case AssignNode():
                self._lower_assign(node)
            case IfNode():
                self._lower_if(node)
            case LoopNode():
                self._lower_loop(node)
            case WhileNode():
                self._lower_while(node)
            case ForNode():
                self._lower_for(node)
            case BreakNode():
                self._lower_break()
            case ContinueNode():
                self._lower_continue()
            case ReturnNode():
                self._lower_return(node)
            case PrintNode():
                self._lower_print(node)
            case InputNode():
                self._lower_input(node)
            case CallNode():
                self._ensure_func()
                self._lower_call(node)
            case CheckCPUNode():
                self._lower_check_cpu(node)
            case PatchPointNode():
                self._lower_patch_point(node)
            case EntityDefNode():
                self._lower_entity_def(node)
            case EntityNode():
                self._ensure_func()
                self._lower_entity_inst(node)
            case TryErrorNode():
                self._lower_try_error(node)
            case BinOpNode():
                self._ensure_func()
                self._lower_expr(node)
            case _:
                pass  # skip unknown

    # ── Function ───────────────────────────────────────────
    def _lower_func_def(self, node: FuncDefNode) -> None:
        func = QFunction(name=node.name or "__anon__")
        for p in node.params:
            vreg = self._alloc.alloc(p)
            func.params.append(vreg)
        self.module.add_function(func)

        prev = self._current_func
        self._current_func = func
        for stmt in node.body:
            self._lower_statement(stmt)
        self._current_func = prev

    def _lower_entity_def(self, node: EntityDefNode) -> None:
        # Register entity type layout: entity_name -> [field_names]
        self.module.entity_types[node.name] = [f[0] for f in node.fields]

    def _lower_entity_inst(self, node: EntityNode) -> VReg:
        self._ensure_func()
        dest = self._alloc.alloc()
        # Find type ID; for now, we use 0 or a placeholder.
        # Ideally, we'd emit an opcode to define the type or use a registry.
        type_id = 0
        self._emit(QInstruction(Opcode.Q_ENTITY_NEW, dest=dest, src1=Immediate(type_id)))
        
        # Set fields
        fields = self.module.entity_types.get(node.type_name, [])
        for field_name, value_node in node.fields:
            val_reg = self._lower_expr(value_node)
            if field_name in fields:
                fidx = fields.index(field_name)
                # Q_SET_FIELD: dest=value, src1=entity, src2=field_index
                self._emit(QInstruction(Opcode.Q_SET_FIELD, dest=val_reg, src1=dest, src2=Immediate(fidx)))
        return dest

    # ── Try / Catch ────────────────────────────────────────
    def _lower_try_error(self, node: TryErrorNode) -> None:
        self._ensure_func()
        catch_label = self._new_label("CATCH")
        end_label = self._new_label("END_TRY")

        self._emit(QInstruction(Opcode.Q_TRY_START, dest=catch_label))
        for stmt in node.try_body:
            self._lower_statement(stmt)
        self._emit(QInstruction(Opcode.Q_TRY_END))
        self._emit(QInstruction(Opcode.Q_JUMP, dest=end_label))

        self._emit(QInstruction(Opcode.Q_LABEL, dest=catch_label))
        # For now, just execute fallback
        for stmt in node.fallback_body:
            self._lower_statement(stmt)
        for _, body in node.error_handlers:
            for stmt in body:
                self._lower_statement(stmt)
        
        self._emit(QInstruction(Opcode.Q_LABEL, dest=end_label))

    # ── Variable declaration ───────────────────────────────
    def _lower_var_decl(self, node: VarDeclNode) -> None:
        self._ensure_func()
        dest = self._alloc.alloc(node.name)
        if node.value:
            src = self._lower_expr(node.value)
            self._emit(QInstruction(Opcode.Q_MOVE, dest=dest, src1=src,
                                    comment=f"var {node.name}"))
        else:
            self._emit(QInstruction(Opcode.Q_LOAD, dest=dest, src1=Immediate(0),
                                    comment=f"var {node.name} = 0"))

    # ── If / Else ──────────────────────────────────────────
    def _lower_if(self, node: IfNode) -> None:
        self._ensure_func()
        cond_reg = self._lower_expr(node.condition) if node.condition else Immediate(0)
        else_label = self._new_label("ELSE")
        end_label = self._new_label("ENDIF")

        self._emit(QInstruction(Opcode.Q_JUMP_IF_NOT, src1=cond_reg, dest=else_label))

        for stmt in node.then_body:
            self._lower_statement(stmt)
        self._emit(QInstruction(Opcode.Q_JUMP, dest=end_label))

        self._emit(QInstruction(Opcode.Q_LABEL, dest=else_label))
        for stmt in node.else_body:
            self._lower_statement(stmt)

        self._emit(QInstruction(Opcode.Q_LABEL, dest=end_label))

    # ── Loop ───────────────────────────────────────────────
    def _lower_loop(self, node: LoopNode) -> None:
        self._ensure_func()
        top = self._new_label("LOOP_TOP")
        cont = self._new_label("LOOP_CONT")
        end = self._new_label("LOOP_END")
        counter = self._alloc.alloc()
        limit_op = self._lower_expr(node.count) if node.count else Immediate(0)

        self._emit(QInstruction(Opcode.Q_LOAD, dest=counter, src1=Immediate(0)))
        self._emit(QInstruction(Opcode.Q_LABEL, dest=top))
        cmp_reg = self._alloc.alloc()
        self._emit(QInstruction(Opcode.Q_CMP_LT, dest=cmp_reg, src1=counter, src2=limit_op))
        self._emit(QInstruction(Opcode.Q_JUMP_IF_NOT, src1=cmp_reg, dest=end))

        self._loop_stack.append((cont, end))
        for stmt in node.body:
            self._lower_statement(stmt)
        self._loop_stack.pop()

        self._emit(QInstruction(Opcode.Q_LABEL, dest=cont))
        one = Immediate(1)
        self._emit(QInstruction(Opcode.Q_ADD, dest=counter, src1=counter, src2=one))
        self._emit(QInstruction(Opcode.Q_JUMP, dest=top))
        self._emit(QInstruction(Opcode.Q_LABEL, dest=end))

    # ── While ──────────────────────────────────────────────
    def _lower_while(self, node: WhileNode) -> None:
        self._ensure_func()
        top = self._new_label("WHILE_TOP")
        end = self._new_label("WHILE_END")

        self._emit(QInstruction(Opcode.Q_LABEL, dest=top))
        cond = self._lower_expr(node.condition) if node.condition else Immediate(0)
        self._emit(QInstruction(Opcode.Q_JUMP_IF_NOT, src1=cond, dest=end))

        self._loop_stack.append((top, end))
        for stmt in node.body:
            self._lower_statement(stmt)
        self._loop_stack.pop()

        self._emit(QInstruction(Opcode.Q_JUMP, dest=top))
        self._emit(QInstruction(Opcode.Q_LABEL, dest=end))

    # ── For ────────────────────────────────────────────────
    def _lower_for(self, node: ForNode) -> None:
        self._ensure_func()
        top = self._new_label("FOR_TOP")
        cont = self._new_label("FOR_CONT")
        end = self._new_label("FOR_END")
        var = self._alloc.alloc(node.var_name)
        start_op = self._lower_expr(node.start) if node.start else Immediate(0)
        end_op = self._lower_expr(node.end) if node.end else Immediate(0)
        step_op = self._lower_expr(node.step) if node.step else Immediate(1)

        self._emit(QInstruction(Opcode.Q_MOVE, dest=var, src1=start_op,
                                comment=f"for {node.var_name} init"))
        self._emit(QInstruction(Opcode.Q_LABEL, dest=top))
        cmp_reg = self._alloc.alloc()
        self._emit(QInstruction(Opcode.Q_CMP_LT, dest=cmp_reg, src1=var, src2=end_op))
        self._emit(QInstruction(Opcode.Q_JUMP_IF_NOT, src1=cmp_reg, dest=end))

        self._loop_stack.append((cont, end))
        for stmt in node.body:
            self._lower_statement(stmt)
        self._loop_stack.pop()

        self._emit(QInstruction(Opcode.Q_LABEL, dest=cont))
        self._emit(QInstruction(Opcode.Q_ADD, dest=var, src1=var, src2=step_op))
        self._emit(QInstruction(Opcode.Q_JUMP, dest=top))
        self._emit(QInstruction(Opcode.Q_LABEL, dest=end))

    # ── Break / Continue ───────────────────────────────────
    def _lower_break(self) -> None:
        self._ensure_func()
        if self._loop_stack:
            _, break_label = self._loop_stack[-1]
            self._emit(QInstruction(Opcode.Q_JUMP, dest=break_label, comment="break"))

    def _lower_continue(self) -> None:
        self._ensure_func()
        if self._loop_stack:
            cont_label, _ = self._loop_stack[-1]
            self._emit(QInstruction(Opcode.Q_JUMP, dest=cont_label, comment="continue"))

    # ── Assignment ─────────────────────────────────────────
    def _lower_assign(self, node: AssignNode) -> None:
        self._ensure_func()
        src = self._lower_expr(node.value) if node.value else Immediate(0)
        dest = self._alloc.lookup(node.name)
        if dest is None:
            dest = self._alloc.alloc(node.name)
        self._emit(QInstruction(Opcode.Q_MOVE, dest=dest, src1=src,
                                comment=f"{node.name} = ..."))

    # ── Return ─────────────────────────────────────────────
    def _lower_return(self, node: ReturnNode) -> None:
        self._ensure_func()
        src = self._lower_expr(node.expr) if node.expr else Immediate(0)
        self._emit(QInstruction(Opcode.Q_RET, src1=src))

    # ── Print ──────────────────────────────────────────────
    def _lower_print(self, node: PrintNode) -> None:
        self._ensure_func()
        src = self._lower_expr(node.expr) if node.expr else Immediate(0)
        self._emit(QInstruction(Opcode.Q_PRINT, src1=src))

    # ── Input ──────────────────────────────────────────────
    def _lower_input(self, node: InputNode) -> None:
        self._ensure_func()
        dest = self._alloc.alloc(node.var_name)
        self._emit(QInstruction(Opcode.Q_INPUT, dest=dest, comment=node.var_name))

    # ── Check CPU (spec §3) ────────────────────────────────
    def _lower_check_cpu(self, node: CheckCPUNode) -> None:
        self._ensure_func()
        patch_id = self._new_patch_id()
        self._emit(QInstruction(Opcode.Q_PATCH_POINT, patch_id=patch_id,
                                comment="CHECK_CPU → dynamic patch"))
        for stmt in node.then_body:
            self._lower_statement(stmt)

    # ── Explicit patch point ───────────────────────────────
    def _lower_patch_point(self, node: PatchPointNode) -> None:
        self._ensure_func()
        pid = node.patch_id or self._new_patch_id()
        self._emit(QInstruction(Opcode.Q_PATCH_POINT, patch_id=pid,
                                comment=f"target={node.target_hint}"))

    # ── Function call ──────────────────────────────────────
    def _lower_call(self, node: CallNode) -> VReg:
        self._ensure_func()
        arg_regs = [self._lower_expr(a) for a in node.args]
        dest = self._alloc.alloc()
        # Move args to param registers R0..Rn
        for i, ar in enumerate(arg_regs):
            self._emit(QInstruction(Opcode.Q_MOVE, dest=VReg(i), src1=ar,
                                    comment=f"arg{i}"))
        self._emit(QInstruction(Opcode.Q_CALL, dest=dest,
                                src1=Immediate(0),
                                comment=node.name))
        return dest

    # ── Expression lowering → returns Operand ──────────────
    def _lower_expr(self, node: ASTNode | None) -> VReg | Immediate:
        if node is None:
            return Immediate(0)

        match node:
            case NumberLiteral():
                dest = self._alloc.alloc()
                self._emit(QInstruction(Opcode.Q_LOAD, dest=dest, src1=Immediate(node.value)))
                return dest

            case IdentifierRef():
                existing = self._alloc.lookup(node.name)
                if existing:
                    return existing
                return self._alloc.alloc(node.name)

            case BinOpNode():
                left = self._lower_expr(node.left)
                right = self._lower_expr(node.right)
                dest = self._alloc.alloc()
                
                # Heuristic for float opcodes
                is_float = False
                if isinstance(node.left, NumberLiteral) and not float(node.left.value).is_integer():
                    is_float = True
                if isinstance(node.right, NumberLiteral) and not float(node.right.value).is_integer():
                    is_float = True
                
                op_map = {
                    "ADD": Opcode.Q_FADD if is_float else Opcode.Q_ADD,
                    "SUB": Opcode.Q_FSUB if is_float else Opcode.Q_SUB,
                    "MUL": Opcode.Q_FMUL if is_float else Opcode.Q_MUL,
                    "DIV": Opcode.Q_FDIV if is_float else Opcode.Q_DIV,
                    "MOD": Opcode.Q_MOD
                }
                opcode = op_map.get(node.op, Opcode.Q_ADD)
                self._emit(QInstruction(opcode, dest=dest, src1=left, src2=right))
                return dest

            case CompareNode():
                left = self._lower_expr(node.left)
                right = self._lower_expr(node.right)
                dest = self._alloc.alloc()
                cmp_map = {"EQ": Opcode.Q_CMP_EQ, "NE": Opcode.Q_CMP_NE,
                           "GT": Opcode.Q_CMP_GT, "LT": Opcode.Q_CMP_LT,
                           "GE": Opcode.Q_CMP_GE, "LE": Opcode.Q_CMP_LE}
                opcode = cmp_map.get(node.op, Opcode.Q_CMP_EQ)
                self._emit(QInstruction(opcode, dest=dest, src1=left, src2=right))
                return dest

            case StringLiteral():
                dest = self._alloc.alloc()
                idx = self.module.add_string(node.value)
                self._emit(QInstruction(Opcode.Q_LOAD_STRING, dest=dest,
                                        src1=Immediate(idx),
                                        string_value=node.value))
                return dest

            case CallNode():
                return self._lower_call(node)

            case LogicOpNode():
                left = self._lower_expr(node.left)
                dest = self._alloc.alloc()
                if node.op == "NOT":
                    # NOT: dest = (left == 0)
                    self._emit(QInstruction(Opcode.Q_CMP_EQ, dest=dest,
                                            src1=left, src2=Immediate(0)))
                else:
                    right = self._lower_expr(node.right)
                    if node.op == "AND":
                        # AND: dest = left * right (both non-zero → non-zero)
                        self._emit(QInstruction(Opcode.Q_MUL, dest=dest,
                                                src1=left, src2=right))
                    else:
                        # OR: dest = left + right (either non-zero → non-zero)
                        self._emit(QInstruction(Opcode.Q_ADD, dest=dest,
                                                src1=left, src2=right))
                return dest

            case MapNode():
                dest = self._alloc.alloc()
                self._emit(QInstruction(Opcode.Q_MAP_NEW, dest=dest))
                for key_node, val_node in node.entries:
                    k = self._lower_expr(key_node)
                    v = self._lower_expr(val_node)
                    self._emit(QInstruction(Opcode.Q_MAP_SET, dest=dest, src1=k, src2=v))
                return dest

            case AccessNode():
                # expr.field_name
                obj_reg = self._lower_expr(node.expr)
                dest = self._alloc.alloc()
                
                # Try to resolve type and field index
                field_idx = 0
                found = False
                if isinstance(node.expr, IdentifierRef):
                    ent_type_name = self._types.get(node.expr.name)
                    if ent_type_name in self.module.entity_types:
                        fields = self.module.entity_types[ent_type_name]
                        if node.field_name in fields:
                            field_idx = fields.index(node.field_name)
                            found = True
                
                if not found:
                    # Fallback to string-based (if VM supports it) or just use 0
                    field_idx = self.module.add_string(node.field_name)
                
                self._emit(QInstruction(Opcode.Q_GET_FIELD, dest=dest, src1=obj_reg, src2=Immediate(field_idx)))
                return dest

            case EntityNode():
                return self._lower_entity_inst(node)

            case _:
                return Immediate(0)
