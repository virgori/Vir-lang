# ═══════════════════════════════════════════════════════════════════════════════
# Vir → Swift Transpiler
# ═══════════════════════════════════════════════════════════════════════════════
# 
# Converts Vir AST to Swift source code.
# 
# Architecture:
#   1. Parse Vir source → AST
#   2. Analyze AST → collect imports, types, native calls
#   3. Generate Swift code → string output
#   4. Optionally compile → call swiftc
#
# The transpiler preserves Vir's semantics while generating idiomatic Swift.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, TextIO
from enum import Enum, auto
from io import StringIO

from .mapping import VirSwiftMapping, SwiftAPIMapping


class NodeType(Enum):
    """AST node types matching Vir's parser."""
    PROGRAM = auto()
    FUNC_DEF = auto()
    VAR_DECL = auto()
    CONST_DECL = auto()
    ASSIGN = auto()
    IF_STMT = auto()
    WHILE_STMT = auto()
    FOR_RANGE = auto()
    LOOP_STMT = auto()
    RETURN_STMT = auto()
    PRINT_STMT = auto()
    BREAK_STMT = auto()
    CONTINUE_STMT = auto()
    BLOCK = auto()
    ENTITY_DEF = auto()
    ENUM_DEF = auto()
    IMPORT_STMT = auto()
    EXPORT_STMT = auto()
    BINARY_OP = auto()
    UNARY_OP = auto()
    CALL = auto()
    INDEX_ACCESS = auto()
    FIELD_ACCESS = auto()
    LITERAL_INT = auto()
    LITERAL_FLOAT = auto()
    LITERAL_STR = auto()
    LITERAL_BOOL = auto()
    IDENTIFIER = auto()
    ARRAY_LITERAL = auto()
    ENTITY_LITERAL = auto()


@dataclass
class AstNode:
    """Simplified AST node for transpilation."""
    node_type: NodeType
    value: Any = None
    name: str = ""
    type_annotation: str = ""
    children: List[AstNode] = field(default_factory=list)
    line: int = 0
    op: str = ""
    

@dataclass
class TranspileContext:
    """Context passed through transpilation for state management."""
    indent_level: int = 0
    in_function: bool = False
    current_function: str = ""
    local_vars: Set[str] = field(default_factory=set)
    global_vars: Set[str] = field(default_factory=set)
    used_imports: Set[str] = field(default_factory=set)
    native_calls: Set[str] = field(default_factory=set)
    errors: List[str] = field(default_factory=list)
    
    def indent(self) -> str:
        return "    " * self.indent_level


class VirToSwiftTranspiler:
    """
    Main transpiler class: converts Vir source code to Swift.
    
    Usage:
        transpiler = VirToSwiftTranspiler()
        swift_code = transpiler.transpile(vir_source)
        transpiler.write_swift_file(swift_code, "output.swift")
    """
    
    def __init__(self):
        self.mapping = VirSwiftMapping()
        self.api_mapping = SwiftAPIMapping()
        self.output = StringIO()
        self.context = TranspileContext()
        
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ENTRY POINTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def transpile(self, vir_source: str) -> str:
        """
        Transpile Vir source code to Swift.
        
        Args:
            vir_source: Vir source code string
            
        Returns:
            Swift source code string
        """
        self.output = StringIO()
        self.context = TranspileContext()
        
        # Translate Vietnamese syntax if present
        vir_source = self.mapping.translate_vietnamese(vir_source)
        
        # Parse and transpile
        lines = vir_source.split('\n')
        swift_lines = self._transpile_lines(lines)
        
        # Generate imports header
        imports = self._generate_imports()
        
        # Combine
        return imports + swift_lines
        
    def transpile_file(self, input_path: str, output_path: str = None) -> str:
        """
        Transpile a .vir file to .swift file.
        
        Args:
            input_path: Path to .vir source file
            output_path: Path for output .swift file (auto-generated if None)
            
        Returns:
            Path to generated Swift file
        """
        if not output_path:
            output_path = input_path.replace('.vir', '.swift')
            
        with open(input_path, 'r', encoding='utf-8') as f:
            vir_source = f.read()
            
        swift_code = self.transpile(vir_source)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(swift_code)
            
        return output_path
        
    # ═══════════════════════════════════════════════════════════════════════════
    # LINE-BY-LINE TRANSPILATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _transpile_lines(self, lines: List[str]) -> str:
        """Process lines and convert to Swift."""
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            indent = self._get_indent(line)
            
            # Skip empty lines and comments
            if not stripped:
                result.append("")
                i += 1
                continue
                
            if stripped.startswith('#'):
                # Convert # comment to // comment
                result.append(indent + "// " + stripped[1:].strip())
                i += 1
                continue
                
            if stripped.startswith('/*') or stripped.startswith('//'):
                result.append(line)
                i += 1
                continue
                
            # Process different statement types
            swift_line = self._transpile_statement(stripped, indent)
            result.append(swift_line)
            i += 1
            
        return '\n'.join(result)
        
    def _transpile_statement(self, stmt: str, indent: str) -> str:
        """Transpile a single statement."""
        
        # Function definition
        if stmt.startswith('func '):
            return indent + self._transpile_func_def(stmt)
            
        # Entity/struct definition
        if stmt.startswith('entity '):
            return indent + self._transpile_entity_def(stmt)
            
        # Enum definition
        if stmt.startswith('enum '):
            return indent + self._transpile_enum_def(stmt)
            
        # Variable declaration
        if stmt.startswith('var '):
            return indent + self._transpile_var_decl(stmt)
            
        # Constant declaration
        if stmt.startswith('const ') or stmt.startswith('let '):
            return indent + self._transpile_const_decl(stmt)
            
        # Import statement
        if stmt.startswith('import '):
            return indent + self._transpile_import(stmt)
            
        # If statement
        if stmt.startswith('if '):
            return indent + self._transpile_if(stmt)
            
        # Else/elif
        if stmt == 'else':
            return indent + "} else {"
        if stmt.startswith('elif ') or stmt.startswith('else if '):
            return indent + self._transpile_elif(stmt)
            
        # While loop
        if stmt.startswith('while '):
            return indent + self._transpile_while(stmt)
            
        # For loop
        if stmt.startswith('for '):
            return indent + self._transpile_for(stmt)
            
        # Loop (infinite)
        if stmt == 'loop':
            return indent + "while true {"
            
        # Return statement
        if stmt.startswith('return ') or stmt.startswith('out '):
            return indent + self._transpile_return(stmt)
            
        # Print statement
        if stmt.startswith('print ') or stmt.startswith('print('):
            return indent + self._transpile_print(stmt)
            
        # End keyword
        if stmt == 'end':
            return indent + "}"
            
        # Then keyword (start of block)
        if stmt == 'then':
            return ""  # Handled in if/while transpilation
            
        # Break/Continue
        if stmt == 'break':
            return indent + "break"
        if stmt == 'continue':
            return indent + "continue"
            
        # Assignment or expression
        return indent + self._transpile_expression_stmt(stmt)
        
    # ═══════════════════════════════════════════════════════════════════════════
    # SPECIFIC STATEMENT TRANSPILERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _transpile_func_def(self, stmt: str) -> str:
        """
        Transpile function definition.
        
        Vir:  func add(a: i32, b: i32) -> i32
        Swift: func add(a: Int32, b: Int32) -> Int32 {
        """
        # Parse: func NAME(PARAMS) -> TYPE
        match = re.match(
            r'func\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(.+?))?(?:\s+then)?$', 
            stmt
        )
        
        if not match:
            # Simple function without params
            simple = re.match(r'func\s+(\w+)(?:\s+then)?$', stmt)
            if simple:
                return f"func {simple.group(1)}() {{"
            return f"// Error: Cannot parse func: {stmt}"
            
        name = match.group(1)
        params_str = match.group(2).strip()
        return_type = match.group(3)
        
        # Translate parameters
        swift_params = self._transpile_params(params_str)
        
        # Translate return type
        swift_return = ""
        if return_type:
            swift_return = f" -> {self.mapping.translate_type(return_type.strip())}"
            
        self.context.in_function = True
        self.context.current_function = name
        
        return f"func {name}({swift_params}){swift_return} {{"
        
    def _transpile_params(self, params_str: str) -> str:
        """Transpile function parameters."""
        if not params_str:
            return ""
            
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if ':' in param:
                name, type_ann = param.split(':', 1)
                swift_type = self.mapping.translate_type(type_ann.strip())
                params.append(f"{name.strip()}: {swift_type}")
            else:
                params.append(param)
                
        return ", ".join(params)
        
    def _transpile_entity_def(self, stmt: str) -> str:
        """
        Transpile entity (struct) definition.
        
        Vir:  entity Point
        Swift: struct Point {
        """
        match = re.match(r'entity\s+(\w+)', stmt)
        if match:
            return f"struct {match.group(1)} {{"
        return f"// Error: Cannot parse entity: {stmt}"
        
    def _transpile_enum_def(self, stmt: str) -> str:
        """
        Transpile enum definition.
        
        Vir:  enum Color
        Swift: enum Color {
        """
        match = re.match(r'enum\s+(\w+)', stmt)
        if match:
            return f"enum {match.group(1)} {{"
        return f"// Error: Cannot parse enum: {stmt}"
        
    def _transpile_var_decl(self, stmt: str) -> str:
        """
        Transpile variable declaration.
        
        Vir:  var x: i32 = 42
        Swift: var x: Int32 = 42
        """
        # Pattern: var NAME: TYPE = VALUE  or  var NAME = VALUE
        match = re.match(r'var\s+(\w+)(?:\s*:\s*([^\s=]+))?\s*=\s*(.+)$', stmt)
        
        if match:
            name = match.group(1)
            type_ann = match.group(2)
            value = match.group(3)
            
            swift_value = self._transpile_expr(value)
            
            if type_ann:
                swift_type = self.mapping.translate_type(type_ann)
                return f"var {name}: {swift_type} = {swift_value}"
            else:
                return f"var {name} = {swift_value}"
                
        # Simple declaration: var x = [...]
        simple = re.match(r'var\s+(\w+)\s*=\s*(.+)$', stmt)
        if simple:
            name = simple.group(1)
            value = self._transpile_expr(simple.group(2))
            return f"var {name} = {value}"
            
        return f"// Error: Cannot parse var: {stmt}"
        
    def _transpile_const_decl(self, stmt: str) -> str:
        """
        Transpile constant declaration.
        
        Vir:  const PI: f64 = 3.14159
        Swift: let PI: Double = 3.14159
        """
        # Remove 'const' or 'let' prefix
        stmt = re.sub(r'^(const|let)\s+', '', stmt)
        
        match = re.match(r'(\w+)(?:\s*:\s*([^\s=]+))?\s*=\s*(.+)$', stmt)
        
        if match:
            name = match.group(1)
            type_ann = match.group(2)
            value = match.group(3)
            
            swift_value = self._transpile_expr(value)
            
            if type_ann:
                swift_type = self.mapping.translate_type(type_ann)
                return f"let {name}: {swift_type} = {swift_value}"
            else:
                return f"let {name} = {swift_value}"
                
        return f"// Error: Cannot parse const: {stmt}"
        
    def _transpile_import(self, stmt: str) -> str:
        """
        Transpile import statement.
        
        Vir:  import "vir/io/file" use File, file_open
        Swift: // Vir import: vir/io/file
        
        Note: Vir imports are handled by the native bridge.
        """
        # Extract module path
        match = re.match(r'import\s+"([^"]+)"(?:\s+use\s+(.+))?', stmt)
        
        if match:
            module = match.group(1)
            symbols = match.group(2) or "all"
            
            # Check if this maps to a Swift framework
            if module.startswith("vir/"):
                return f"// Vir import: {module} ({symbols})"
            else:
                # Assume it's a Swift framework
                self.context.used_imports.add(module)
                return f"import {module}"
                
        # Simple import
        match = re.match(r'import\s+(\w+)', stmt)
        if match:
            framework = match.group(1)
            self.context.used_imports.add(framework)
            return f"import {framework}"
            
        return f"// Error: Cannot parse import: {stmt}"
        
    def _transpile_if(self, stmt: str) -> str:
        """
        Transpile if statement.
        
        Vir:  if x > 0 then
        Swift: if x > 0 {
        """
        # Remove 'then' suffix if present
        stmt = re.sub(r'\s+then$', '', stmt)
        
        # Extract condition
        match = re.match(r'if\s+(.+)$', stmt)
        if match:
            cond = self._transpile_expr(match.group(1))
            return f"if {cond} {{"
            
        return f"// Error: Cannot parse if: {stmt}"
        
    def _transpile_elif(self, stmt: str) -> str:
        """Transpile elif statement."""
        stmt = re.sub(r'^(elif|else\s+if)\s+', '', stmt)
        stmt = re.sub(r'\s+then$', '', stmt)
        cond = self._transpile_expr(stmt)
        return f"}} else if {cond} {{"
        
    def _transpile_while(self, stmt: str) -> str:
        """
        Transpile while loop.
        
        Vir:  while x > 0
        Swift: while x > 0 {
        """
        stmt = re.sub(r'\s+then$', '', stmt)
        match = re.match(r'while\s+(.+)$', stmt)
        if match:
            cond = self._transpile_expr(match.group(1))
            return f"while {cond} {{"
        return f"// Error: Cannot parse while: {stmt}"
        
    def _transpile_for(self, stmt: str) -> str:
        """
        Transpile for loop.
        
        Vir:  for i in 0..10
        Swift: for i in 0..<10 {
        """
        match = re.match(r'for\s+(\w+)\s+in\s+(.+?)(?:\s+then)?$', stmt)
        if match:
            var = match.group(1)
            iter_expr = match.group(2)
            
            # Transpile the entire iterator expression (handles len(), etc.)
            iter_expr = self._transpile_expr(iter_expr)
            
            return f"for {var} in {iter_expr} {{"
            
        return f"// Error: Cannot parse for: {stmt}"
        
    def _transpile_range(self, expr: str) -> str:
        """Transpile range expressions."""
        # Exclusive: 0..10 → 0..<10
        expr = re.sub(r'(\d+|\w+(?:\([^)]*\))?|\[[^\]]*\])\.\.(\d+|\w+(?:\([^)]*\))?|\[[^\]]*\]\.count)', r'\1..<\2', expr)
        # Inclusive: 0..=10 → 0...10
        expr = re.sub(r'(\d+|\w+(?:\([^)]*\))?|\[[^\]]*\])\.\.=(\d+|\w+(?:\([^)]*\))?|\[[^\]]*\]\.count)', r'\1...\2', expr)
        return expr
        
    def _transpile_return(self, stmt: str) -> str:
        """
        Transpile return statement.
        
        Vir:  out x + y  or  return x + y
        Swift: return x + y
        """
        match = re.match(r'(out|return)\s+(.+)$', stmt)
        if match:
            value = self._transpile_expr(match.group(2))
            return f"return {value}"
        # Empty return
        if stmt in ('out', 'return'):
            return "return"
        return f"// Error: Cannot parse return: {stmt}"
        
    def _transpile_print(self, stmt: str) -> str:
        """
        Transpile print statement.
        
        Vir:  print x
        Swift: print(x)
        """
        # print(x) format
        match = re.match(r'print\s*\((.+)\)$', stmt)
        if match:
            args = self._transpile_expr(match.group(1))
            return f"print({args})"
            
        # print x format (without parens)
        match = re.match(r'print\s+(.+)$', stmt)
        if match:
            args = self._transpile_expr(match.group(1))
            return f"print({args})"
            
        return "print()"
        
    def _transpile_expression_stmt(self, stmt: str) -> str:
        """Transpile an expression statement (assignment or call)."""
        # Field definition in entity/struct (name: type)
        match = re.match(r'^(\w+)\s*:\s*([^\s=]+)\s*$', stmt)
        if match:
            name = match.group(1)
            type_ann = self.mapping.translate_type(match.group(2))
            return f"var {name}: {type_ann}"
            
        # Enum variant with value: Red = 0
        match = re.match(r'^(\w+)\s*=\s*(\d+)\s*$', stmt)
        if match:
            return f"case {match.group(1)} = {match.group(2)}"
            
        # Enum variant without value: Circle
        match = re.match(r'^([A-Z]\w*)\s*$', stmt)
        if match:
            return f"case {match.group(1)}"
            
        # Assignment
        if '=' in stmt and not any(stmt.startswith(op) for op in ['==', '!=', '<=', '>=']):
            parts = stmt.split('=', 1)
            if len(parts) == 2:
                lhs = parts[0].strip()
                rhs = self._transpile_expr(parts[1].strip())
                return f"{lhs} = {rhs}"
                
        # Expression (function call, etc)
        return self._transpile_expr(stmt)
        
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPRESSION TRANSPILATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _transpile_expr(self, expr: str) -> str:
        """Transpile an expression."""
        expr = expr.strip()
        
        # Handle empty
        if not expr:
            return ""
            
        # Handle vec_push specially (can have nested braces)
        if expr.startswith('vec_push('):
            return self._transpile_vec_push(expr)
            
        # String literal
        if expr.startswith('"') and expr.endswith('"'):
            return expr
            
        # Array literal: [1, 2, 3]
        if expr.startswith('[') and expr.endswith(']'):
            return self._transpile_array_literal(expr)
            
        # Entity literal: MyEntity { field: value }
        if '{' in expr and '}' in expr:
            return self._transpile_entity_literal(expr)
            
        # Handle logical operators
        expr = re.sub(r'\band\b', '&&', expr)
        expr = re.sub(r'\bor\b', '||', expr)
        expr = re.sub(r'\bnot\b', '!', expr)
        
        # Handle boolean literals
        expr = re.sub(r'\bnone\b', 'nil', expr)
        
        # Handle range operators
        expr = self._transpile_range(expr)
        
        # Handle method calls on builtins
        # len(arr) → arr.count
        expr = re.sub(r'len\(([^)]+)\)', r'\1.count', expr)
        
        # vec_push(arr, x) → arr.append(x)
        match = re.search(r'vec_push\(([^,]+),\s*(.+)\)', expr)
        if match:
            arr = match.group(1)
            val = self._transpile_expr(match.group(2))
            expr = expr.replace(match.group(0), f'{arr}.append({val})')
        
        # push(arr, x) → arr.append(x)
        match = re.search(r'push\(([^,]+),\s*(.+)\)', expr)
        if match:
            arr = match.group(1)
            val = match.group(2)
            expr = expr.replace(match.group(0), f'{arr}.append({val})')
            
        # vec_new<T>() → [T]()
        expr = re.sub(r'vec_new<([^>]+)>\(\)', r'[\1]()', expr)
        
        # str_new("x") → "x"
        expr = re.sub(r'str_new\(([^)]+)\)', r'\1', expr)
        
        # str_cat(a, b) → (a + b) - properly handles strings with commas
        while 'str_cat(' in expr:
            idx = expr.find('str_cat(')
            if idx == -1:
                break
            
            # Parse arguments respecting string literals and nested parens
            start = idx + 8  # len("str_cat(")
            depth = 1
            in_string = False
            string_char = None
            first_arg_end = -1
            i = start
            
            while i < len(expr) and depth > 0:
                c = expr[i]
                
                # Handle string literals
                if c in '"\'':
                    if not in_string:
                        in_string = True
                        string_char = c
                    elif c == string_char and (i == 0 or expr[i-1] != '\\'):
                        in_string = False
                elif not in_string:
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1
                    elif c == ',' and depth == 1 and first_arg_end == -1:
                        first_arg_end = i
                i += 1
            
            if first_arg_end > 0 and depth == 0:
                end = i
                arg1 = expr[start:first_arg_end].strip()
                arg2 = expr[first_arg_end + 1:end - 1].strip()
                replacement = f'({arg1} + {arg2})'
                expr = expr[:idx] + replacement + expr[end:]
            else:
                break
        
        # Handle enum access: EnumName::Variant → EnumName.Variant
        expr = re.sub(r'(\w+)::(\w+)', r'\1.\2', expr)
        
        # Handle optional unwrap: x! → x!
        # (Same in both languages)
        
        return expr
        
    def _transpile_array_literal(self, expr: str) -> str:
        """Transpile array literal."""
        # Remove brackets
        inner = expr[1:-1].strip()
        if not inner:
            return "[]"
            
        # Transpile each element
        elements = []
        depth = 0
        current = ""
        
        for char in inner:
            if char in '([{':
                depth += 1
            elif char in ')]}':
                depth -= 1
            elif char == ',' and depth == 0:
                elements.append(self._transpile_expr(current.strip()))
                current = ""
                continue
            current += char
            
        if current.strip():
            elements.append(self._transpile_expr(current.strip()))
            
        return f"[{', '.join(elements)}]"
        
    def _transpile_entity_literal(self, expr: str) -> str:
        """
        Transpile entity literal.
        
        Vir:  Point { x: 10, y: 20 }
        Swift: Point(x: 10, y: 20)
        """
        match = re.match(r'(\w+)\s*\{([^}]+)\}', expr)
        if match:
            name = match.group(1)
            fields = match.group(2).strip()
            
            # Transpile field values
            swift_fields = []
            for field in fields.split(','):
                field = field.strip()
                if ':' in field:
                    fname, fval = field.split(':', 1)
                    fval = self._transpile_expr(fval.strip())
                    swift_fields.append(f"{fname.strip()}: {fval}")
                else:
                    swift_fields.append(self._transpile_expr(field))
                    
            return f"{name}({', '.join(swift_fields)})"
            
        return expr
        
    def _transpile_vec_push(self, expr: str) -> str:
        """
        Transpile vec_push with proper handling of nested braces.
        
        Vir:  vec_push(points, Point { x: 1.0, y: 2.0 })
        Swift: points.append(Point(x: 1.0, y: 2.0))
        """
        # Remove 'vec_push(' prefix and ')' suffix
        inner = expr[9:-1]  # len("vec_push(") = 9
        
        # Find the first comma at depth 0 (separates array from value)
        depth = 0
        split_pos = -1
        
        for i, char in enumerate(inner):
            if char in '([{':
                depth += 1
            elif char in ')]}':
                depth -= 1
            elif char == ',' and depth == 0:
                split_pos = i
                break
                
        if split_pos > 0:
            arr_name = inner[:split_pos].strip()
            value = inner[split_pos + 1:].strip()
            swift_value = self._transpile_expr(value)
            return f"{arr_name}.append({swift_value})"
            
        return expr  # Fallback
        
    # ═══════════════════════════════════════════════════════════════════════════
    # IMPORT GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_imports(self) -> str:
        """Generate Swift import statements."""
        imports = ["import Foundation"]  # Always include Foundation
        
        for imp in sorted(self.context.used_imports):
            if imp != "Foundation":
                imports.append(f"import {imp}")
                
        if imports:
            return '\n'.join(imports) + '\n\n'
        return ""
        
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _get_indent(self, line: str) -> str:
        """Extract leading whitespace from a line."""
        match = re.match(r'^(\s*)', line)
        return match.group(1) if match else ""


# ═══════════════════════════════════════════════════════════════════════════════
# SWIFT CODE TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

SWIFT_MAIN_TEMPLATE = '''\
// Generated by Vir Transpiler
// Source: {source_file}
// Date: {date}

{imports}

{code}

// Entry point
@main
struct VirApp {{
    static func main() {{
        {entry_call}
    }}
}}
'''

SWIFT_NATIVE_BRIDGE_TEMPLATE = '''\
// Native Bridge: Links Vir code to native C/C++/Rust libraries

import Foundation

/// Bridge to native performance library
final class VirNativeBridge {{
    
    static let shared = VirNativeBridge()
    
    private init() {{
        // Load native library
        // dlopen("libvir_native.dylib", RTLD_NOW)
    }}
    
    // Native function declarations will be added here
    {native_declarations}
}}
'''

SWIFTUI_APP_TEMPLATE = '''\
// Generated SwiftUI App from Vir
// Source: {source_file}

import SwiftUI

{code}

@main
struct VirGeneratedApp: App {{
    var body: some Scene {{
        WindowGroup {{
            ContentView()
        }}
    }}
}}
'''
