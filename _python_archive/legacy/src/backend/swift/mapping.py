# ═══════════════════════════════════════════════════════════════════════════════
# Vir → Swift Mapping Table
# ═══════════════════════════════════════════════════════════════════════════════
# 
# This module defines the syntax mapping between Vir and Swift.
# Each Vir construct maps to its Swift equivalent.
#
# Mapping Categories:
#   1. Keywords & Control Flow
#   2. Types & Declarations
#   3. Operators
#   4. Built-in Functions
#   5. Standard Library Bridges
# ═══════════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum, auto


class MappingCategory(Enum):
    """Categories for syntax mappings."""
    KEYWORD = auto()
    TYPE = auto()
    OPERATOR = auto()
    BUILTIN = auto()
    CONTROL_FLOW = auto()
    DECLARATION = auto()
    EXPRESSION = auto()
    PATTERN = auto()


@dataclass
class SyntaxMapping:
    """Represents a mapping from Vir syntax to Swift syntax."""
    vir_syntax: str
    swift_syntax: str
    category: MappingCategory
    requires_import: Optional[str] = None
    notes: str = ""
    transformer: Optional[Callable] = None


@dataclass 
class TypeMapping:
    """Maps Vir types to Swift types."""
    vir_type: str
    swift_type: str
    is_optional: bool = False
    generic_params: List[str] = field(default_factory=list)


class VirSwiftMapping:
    """
    Central mapping table for Vir → Swift transpilation.
    
    Usage:
        mapping = VirSwiftMapping()
        swift_code = mapping.translate_keyword("func")  # → "func"
        swift_type = mapping.translate_type("i64")      # → "Int64"
    """
    
    def __init__(self):
        self._init_keyword_mappings()
        self._init_type_mappings()
        self._init_operator_mappings()
        self._init_builtin_mappings()
        self._init_control_flow_mappings()
        self._init_pattern_mappings()
        
    # ═══════════════════════════════════════════════════════════════════════════
    # 1. KEYWORD MAPPINGS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _init_keyword_mappings(self):
        """Initialize keyword-to-keyword mappings."""
        self.keywords: Dict[str, SyntaxMapping] = {
            # Function definitions
            "func": SyntaxMapping("func", "func", MappingCategory.KEYWORD),
            "end": SyntaxMapping("end", "}", MappingCategory.KEYWORD, 
                                 notes="Vir uses 'end' to close blocks"),
            "out": SyntaxMapping("out", "return", MappingCategory.KEYWORD),
            "return": SyntaxMapping("return", "return", MappingCategory.KEYWORD),
            
            # Variable declarations  
            "var": SyntaxMapping("var", "var", MappingCategory.DECLARATION),
            "const": SyntaxMapping("const", "let", MappingCategory.DECLARATION),
            "let": SyntaxMapping("let", "let", MappingCategory.DECLARATION),
            
            # Control flow
            "if": SyntaxMapping("if", "if", MappingCategory.CONTROL_FLOW),
            "else": SyntaxMapping("else", "} else {", MappingCategory.CONTROL_FLOW),
            "elif": SyntaxMapping("elif", "} else if", MappingCategory.CONTROL_FLOW),
            "then": SyntaxMapping("then", "{", MappingCategory.CONTROL_FLOW),
            "while": SyntaxMapping("while", "while", MappingCategory.CONTROL_FLOW),
            "for": SyntaxMapping("for", "for", MappingCategory.CONTROL_FLOW),
            "in": SyntaxMapping("in", "in", MappingCategory.CONTROL_FLOW),
            "loop": SyntaxMapping("loop", "while true {", MappingCategory.CONTROL_FLOW),
            "break": SyntaxMapping("break", "break", MappingCategory.CONTROL_FLOW),
            "continue": SyntaxMapping("continue", "continue", MappingCategory.CONTROL_FLOW),
            
            # Type definitions
            "entity": SyntaxMapping("entity", "struct", MappingCategory.DECLARATION,
                                    notes="Vir 'entity' → Swift 'struct'"),
            "struct": SyntaxMapping("struct", "struct", MappingCategory.DECLARATION),
            "enum": SyntaxMapping("enum", "enum", MappingCategory.DECLARATION),
            "class": SyntaxMapping("class", "class", MappingCategory.DECLARATION),
            "protocol": SyntaxMapping("protocol", "protocol", MappingCategory.DECLARATION),
            
            # Module system
            "import": SyntaxMapping("import", "import", MappingCategory.KEYWORD),
            "use": SyntaxMapping("use", "//use:", MappingCategory.KEYWORD,
                                 notes="Vir selective import handled specially"),
            "export": SyntaxMapping("export", "public", MappingCategory.KEYWORD),
            "module": SyntaxMapping("module", "//module:", MappingCategory.KEYWORD),
            
            # Boolean literals
            "true": SyntaxMapping("true", "true", MappingCategory.EXPRESSION),
            "false": SyntaxMapping("false", "false", MappingCategory.EXPRESSION),
            "none": SyntaxMapping("none", "nil", MappingCategory.EXPRESSION),
            "nil": SyntaxMapping("nil", "nil", MappingCategory.EXPRESSION),
            
            # Special
            "self": SyntaxMapping("self", "self", MappingCategory.EXPRESSION),
            "super": SyntaxMapping("super", "super", MappingCategory.EXPRESSION),
        }
        
        # Vietnamese keyword aliases (từ hello.vri)
        self.vn_keywords: Dict[str, str] = {
            "Ta có hàm": "func",
            "Nếu": "if",
            "ngược lại": "else",
            "lặp lại": "for _ in 0..<",
            "trả về": "return",
            "cho biến": "var",
            "in ra": "print",
            "máy rảnh": "/* CPU idle check */",
        }
        
    # ═══════════════════════════════════════════════════════════════════════════
    # 2. TYPE MAPPINGS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _init_type_mappings(self):
        """Initialize Vir type → Swift type mappings."""
        self.types: Dict[str, TypeMapping] = {
            # Integers
            "i8": TypeMapping("i8", "Int8"),
            "i16": TypeMapping("i16", "Int16"),
            "i32": TypeMapping("i32", "Int32"),
            "i64": TypeMapping("i64", "Int64"),
            "int": TypeMapping("int", "Int"),
            
            # Unsigned integers
            "u8": TypeMapping("u8", "UInt8"),
            "u16": TypeMapping("u16", "UInt16"),
            "u32": TypeMapping("u32", "UInt32"),
            "u64": TypeMapping("u64", "UInt64"),
            "uint": TypeMapping("uint", "UInt"),
            
            # Floating point
            "f32": TypeMapping("f32", "Float"),
            "f64": TypeMapping("f64", "Double"),
            "float": TypeMapping("float", "Double"),
            
            # Boolean
            "bool": TypeMapping("bool", "Bool"),
            
            # String
            "str": TypeMapping("str", "String"),
            "String": TypeMapping("String", "String"),
            
            # Collections
            "Vec": TypeMapping("Vec", "Array", generic_params=["T"]),
            "Dict": TypeMapping("Dict", "Dictionary", generic_params=["K", "V"]),
            "Set": TypeMapping("Set", "Set", generic_params=["T"]),
            "Array": TypeMapping("Array", "[T]", generic_params=["T"]),
            
            # Optional
            "Option": TypeMapping("Option", "Optional", is_optional=True, 
                                  generic_params=["T"]),
            "Result": TypeMapping("Result", "Result", generic_params=["T", "E"]),
            
            # Void
            "void": TypeMapping("void", "Void"),
            "()": TypeMapping("()", "Void"),
            
            # Any
            "any": TypeMapping("any", "Any"),
            "dyn": TypeMapping("dyn", "any"),
            
            # Raw pointers (for native bindings)
            "ptr": TypeMapping("ptr", "UnsafeMutableRawPointer"),
            "const_ptr": TypeMapping("const_ptr", "UnsafeRawPointer"),
        }
        
    # ═══════════════════════════════════════════════════════════════════════════
    # 3. OPERATOR MAPPINGS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _init_operator_mappings(self):
        """Initialize operator mappings."""
        self.operators: Dict[str, SyntaxMapping] = {
            # Arithmetic (same in both)
            "+": SyntaxMapping("+", "+", MappingCategory.OPERATOR),
            "-": SyntaxMapping("-", "-", MappingCategory.OPERATOR),
            "*": SyntaxMapping("*", "*", MappingCategory.OPERATOR),
            "/": SyntaxMapping("/", "/", MappingCategory.OPERATOR),
            "%": SyntaxMapping("%", "%", MappingCategory.OPERATOR),
            
            # Comparison (same in both)
            "==": SyntaxMapping("==", "==", MappingCategory.OPERATOR),
            "!=": SyntaxMapping("!=", "!=", MappingCategory.OPERATOR),
            "<": SyntaxMapping("<", "<", MappingCategory.OPERATOR),
            ">": SyntaxMapping(">", ">", MappingCategory.OPERATOR),
            "<=": SyntaxMapping("<=", "<=", MappingCategory.OPERATOR),
            ">=": SyntaxMapping(">=", ">=", MappingCategory.OPERATOR),
            
            # Logical
            "and": SyntaxMapping("and", "&&", MappingCategory.OPERATOR),
            "or": SyntaxMapping("or", "||", MappingCategory.OPERATOR),
            "not": SyntaxMapping("not", "!", MappingCategory.OPERATOR),
            "&&": SyntaxMapping("&&", "&&", MappingCategory.OPERATOR),
            "||": SyntaxMapping("||", "||", MappingCategory.OPERATOR),
            "!": SyntaxMapping("!", "!", MappingCategory.OPERATOR),
            
            # Bitwise
            "&": SyntaxMapping("&", "&", MappingCategory.OPERATOR),
            "|": SyntaxMapping("|", "|", MappingCategory.OPERATOR),
            "^": SyntaxMapping("^", "^", MappingCategory.OPERATOR),
            "~": SyntaxMapping("~", "~", MappingCategory.OPERATOR),
            "<<": SyntaxMapping("<<", "<<", MappingCategory.OPERATOR),
            ">>": SyntaxMapping(">>", ">>", MappingCategory.OPERATOR),
            
            # Assignment
            "=": SyntaxMapping("=", "=", MappingCategory.OPERATOR),
            "+=": SyntaxMapping("+=", "+=", MappingCategory.OPERATOR),
            "-=": SyntaxMapping("-=", "-=", MappingCategory.OPERATOR),
            "*=": SyntaxMapping("*=", "*=", MappingCategory.OPERATOR),
            "/=": SyntaxMapping("/=", "/=", MappingCategory.OPERATOR),
            
            # Range
            "..": SyntaxMapping("..", "..<", MappingCategory.OPERATOR,
                                notes="Vir exclusive range"),
            "..=": SyntaxMapping("..=", "...", MappingCategory.OPERATOR,
                                 notes="Vir inclusive range"),
                                 
            # Optional/null coalescing  
            "??": SyntaxMapping("??", "??", MappingCategory.OPERATOR),
            "?.": SyntaxMapping("?.", "?.", MappingCategory.OPERATOR),
            
            # Type cast
            "as": SyntaxMapping("as", "as", MappingCategory.OPERATOR),
            "as!": SyntaxMapping("as!", "as!", MappingCategory.OPERATOR),
            "as?": SyntaxMapping("as?", "as?", MappingCategory.OPERATOR),
        }
        
    # ═══════════════════════════════════════════════════════════════════════════
    # 4. BUILTIN FUNCTION MAPPINGS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _init_builtin_mappings(self):
        """Initialize built-in function mappings."""
        self.builtins: Dict[str, SyntaxMapping] = {
            # I/O
            "print": SyntaxMapping("print", "print", MappingCategory.BUILTIN),
            "println": SyntaxMapping("println", "print", MappingCategory.BUILTIN,
                                     notes="Swift print adds newline by default"),
            "input": SyntaxMapping("input", "readLine", MappingCategory.BUILTIN),
            
            # String operations
            "len": SyntaxMapping("len", ".count", MappingCategory.BUILTIN,
                                 notes="Method call, not function"),
            "str_len": SyntaxMapping("str_len", ".count", MappingCategory.BUILTIN),
            "str_cat": SyntaxMapping("str_cat", "+", MappingCategory.BUILTIN,
                                     notes="String concatenation in Swift"),
            "str_eq": SyntaxMapping("str_eq", "==", MappingCategory.BUILTIN),
            
            # Array operations
            "push": SyntaxMapping("push", ".append", MappingCategory.BUILTIN),
            "pop": SyntaxMapping("pop", ".removeLast", MappingCategory.BUILTIN),
            "vec_new": SyntaxMapping("vec_new", "[]", MappingCategory.BUILTIN),
            "vec_len": SyntaxMapping("vec_len", ".count", MappingCategory.BUILTIN),
            "vec_get": SyntaxMapping("vec_get", "[]", MappingCategory.BUILTIN,
                                     notes="Array subscript"),
            "vec_push": SyntaxMapping("vec_push", ".append", MappingCategory.BUILTIN),
            
            # Memory (for native bindings)
            "alloc": SyntaxMapping("alloc", "UnsafeMutableRawPointer.allocate", 
                                   MappingCategory.BUILTIN,
                                   requires_import="Foundation"),
            "dealloc": SyntaxMapping("dealloc", ".deallocate", MappingCategory.BUILTIN),
            
            # Type conversions
            "i_to_str": SyntaxMapping("i_to_str", "String", MappingCategory.BUILTIN,
                                      notes="String(intValue)"),
            "str_to_i": SyntaxMapping("str_to_i", "Int", MappingCategory.BUILTIN,
                                      notes="Int(strValue)"),
            
            # File I/O (requires Foundation)
            "file_open": SyntaxMapping("file_open", "FileHandle", 
                                       MappingCategory.BUILTIN,
                                       requires_import="Foundation"),
            "file_read": SyntaxMapping("file_read", ".readData", 
                                       MappingCategory.BUILTIN),
            "file_write": SyntaxMapping("file_write", ".write", 
                                        MappingCategory.BUILTIN),
            "file_close": SyntaxMapping("file_close", ".closeFile", 
                                        MappingCategory.BUILTIN),
            
            # Process
            "exit_prog": SyntaxMapping("exit_prog", "exit", MappingCategory.BUILTIN,
                                       requires_import="Foundation"),
            "exit": SyntaxMapping("exit", "exit", MappingCategory.BUILTIN),
            
            # Math (requires Foundation)
            "sqrt": SyntaxMapping("sqrt", "sqrt", MappingCategory.BUILTIN,
                                  requires_import="Foundation"),
            "abs": SyntaxMapping("abs", "abs", MappingCategory.BUILTIN),
            "min": SyntaxMapping("min", "min", MappingCategory.BUILTIN),
            "max": SyntaxMapping("max", "max", MappingCategory.BUILTIN),
        }
        
    # ═══════════════════════════════════════════════════════════════════════════
    # 5. CONTROL FLOW PATTERNS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _init_control_flow_mappings(self):
        """Initialize control flow pattern mappings."""
        self.control_patterns: Dict[str, str] = {
            # Function definition
            "func NAME(PARAMS) -> TYPE": "func NAME(PARAMS) -> TYPE {",
            "func NAME(PARAMS)": "func NAME(PARAMS) {",
            
            # If statement  
            "if COND then": "if COND {",
            "if COND": "if COND {",
            
            # Loops
            "while COND": "while COND {",
            "for VAR in ITER": "for VAR in ITER {",
            "loop": "while true {",
            
            # Match/Switch
            "match VAR": "switch VAR {",
            "case PATTERN:": "case PATTERN:",
            "default:": "default:",
            
            # Entity/Struct
            "entity NAME": "struct NAME {",
            "struct NAME": "struct NAME {",
            
            # Enum
            "enum NAME": "enum NAME {",
        }
        
    # ═══════════════════════════════════════════════════════════════════════════
    # 6. PATTERN TRANSFORMATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _init_pattern_mappings(self):
        """Initialize complex pattern transformations."""
        self.patterns = {
            # Entity/struct initialization
            # Vir: MyEntity { field: value, field2: value2 }
            # Swift: MyEntity(field: value, field2: value2)
            "entity_init": lambda name, fields: f"{name}({fields})",
            
            # Option handling
            # Vir: if let x = optional then ... end
            # Swift: if let x = optional { ... }
            "if_let": lambda var, opt, body: f"if let {var} = {opt} {{\n{body}\n}}",
            
            # Guard
            # Vir: guard COND else return end  
            # Swift: guard COND else { return }
            "guard": lambda cond, fallback: f"guard {cond} else {{ {fallback} }}",
            
            # Closure/lambda
            # Vir: |x, y| -> x + y
            # Swift: { x, y in x + y }
            "closure": lambda params, body: f"{{ {params} in {body} }}",
            
            # Range iteration
            # Vir: for i in 0..10
            # Swift: for i in 0..<10
            "range_exclusive": lambda start, end: f"{start}..<{end}",
            "range_inclusive": lambda start, end: f"{start}...{end}",
        }
        
    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════
    
    def translate_keyword(self, vir_keyword: str) -> str:
        """Translate a Vir keyword to Swift."""
        if vir_keyword in self.keywords:
            return self.keywords[vir_keyword].swift_syntax
        return vir_keyword
        
    def translate_type(self, vir_type: str) -> str:
        """Translate a Vir type to Swift type."""
        # Handle generic types like Vec<i32>
        if "<" in vir_type:
            base, generic_part = vir_type.split("<", 1)
            generic_part = generic_part.rstrip(">")
            
            if base in self.types:
                swift_base = self.types[base].swift_type
                # Recursively translate generic parameters
                swift_generic = self.translate_type(generic_part)
                
                if base == "Vec":
                    return f"[{swift_generic}]"
                elif base == "Dict":
                    # Dict<K, V> → [K: V]
                    parts = generic_part.split(",")
                    if len(parts) == 2:
                        k = self.translate_type(parts[0].strip())
                        v = self.translate_type(parts[1].strip())
                        return f"[{k}: {v}]"
                elif base == "Option":
                    return f"{swift_generic}?"
                else:
                    return f"{swift_base}<{swift_generic}>"
                    
        if vir_type in self.types:
            return self.types[vir_type].swift_type
        return vir_type
        
    def translate_operator(self, vir_op: str) -> str:
        """Translate a Vir operator to Swift."""
        if vir_op in self.operators:
            return self.operators[vir_op].swift_syntax
        return vir_op
        
    def translate_builtin(self, name: str) -> SyntaxMapping:
        """Get the mapping for a built-in function."""
        return self.builtins.get(name)
        
    def get_required_imports(self, used_builtins: List[str]) -> List[str]:
        """Get Swift imports required for the used built-ins."""
        imports = set()
        for name in used_builtins:
            mapping = self.builtins.get(name)
            if mapping and mapping.requires_import:
                imports.add(mapping.requires_import)
        return sorted(imports)
        
    def translate_vietnamese(self, vn_code: str) -> str:
        """Translate Vietnamese Vir syntax to standard Vir."""
        result = vn_code
        for vn, en in self.vn_keywords.items():
            result = result.replace(vn, en)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# SWIFT-SPECIFIC API MAPPINGS
# ═══════════════════════════════════════════════════════════════════════════════

class SwiftAPIMapping:
    """
    Maps Vir standard library calls to Swift/UIKit/Foundation equivalents.
    
    This enables Vir code to call native iOS/macOS APIs seamlessly.
    """
    
    def __init__(self):
        self._init_foundation_mappings()
        self._init_uikit_mappings()
        self._init_swiftui_mappings()
        
    def _init_foundation_mappings(self):
        """Foundation framework mappings."""
        self.foundation = {
            # Date/Time
            "now": "Date()",
            "timestamp": "Date().timeIntervalSince1970",
            
            # FileManager
            "file_exists": "FileManager.default.fileExists",
            "create_dir": "FileManager.default.createDirectory",
            "list_dir": "FileManager.default.contentsOfDirectory",
            "remove_file": "FileManager.default.removeItem",
            
            # UserDefaults
            "prefs_get": "UserDefaults.standard.object",
            "prefs_set": "UserDefaults.standard.set",
            
            # JSON
            "json_encode": "JSONEncoder().encode",
            "json_decode": "JSONDecoder().decode",
            
            # URL/Network
            "url_new": "URL(string:)",
            "fetch_data": "URLSession.shared.data",
        }
        
    def _init_uikit_mappings(self):
        """UIKit framework mappings (iOS)."""
        self.uikit = {
            # Views
            "view_new": "UIView()",
            "label_new": "UILabel()",
            "button_new": "UIButton()",
            "image_view_new": "UIImageView()",
            
            # Layout
            "add_subview": ".addSubview",
            "remove_from_parent": ".removeFromSuperview",
            "set_frame": ".frame =",
            
            # Colors
            "color_new": "UIColor",
            "color_red": "UIColor.red",
            "color_blue": "UIColor.blue",
            "color_white": "UIColor.white",
            "color_black": "UIColor.black",
        }
        
    def _init_swiftui_mappings(self):
        """SwiftUI framework mappings."""
        self.swiftui = {
            # Views
            "text": "Text",
            "image": "Image",
            "button": "Button",
            "vstack": "VStack",
            "hstack": "HStack",
            "zstack": "ZStack",
            "list": "List",
            "scroll_view": "ScrollView",
            
            # Modifiers
            "padding": ".padding",
            "background": ".background",
            "foreground": ".foregroundColor",
            "font": ".font",
            "frame": ".frame",
        }
        
    def get_import_for_api(self, api_name: str) -> Optional[str]:
        """Get the required import for an API."""
        if api_name in self.foundation:
            return "Foundation"
        elif api_name in self.uikit:
            return "UIKit"
        elif api_name in self.swiftui:
            return "SwiftUI"
        return None
