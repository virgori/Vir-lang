# ═══════════════════════════════════════════════════════════════════════════════
# Vir Native Bridge — Swift ↔ C/C++/Rust FFI
# ═══════════════════════════════════════════════════════════════════════════════
# 
# This module generates Swift code to interface with native static libraries.
# 
# Architecture (Vỏ Vir - Nhân Native):
#   1. Heavy computation written in C/C++/Rust
#   2. Compiled to static library (.a or .framework)
#   3. Swift bridge generated automatically
#   4. Vir transpiled code calls Swift bridge
#
# The bridge handles:
#   - Type marshalling (Vir types ↔ C types ↔ Swift types)
#   - Memory management hints
#   - Error translation
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum, auto


class NativeType(Enum):
    """C/Rust type categories for FFI."""
    VOID = auto()
    INT8 = auto()
    INT16 = auto()
    INT32 = auto()
    INT64 = auto()
    UINT8 = auto()
    UINT16 = auto()
    UINT32 = auto()
    UINT64 = auto()
    FLOAT32 = auto()
    FLOAT64 = auto()
    BOOL = auto()
    POINTER = auto()
    CONST_POINTER = auto()
    STRING = auto()
    OPAQUE = auto()


@dataclass
class NativeFunction:
    """Represents a native function to be bridged."""
    name: str
    c_name: str  # Actual symbol name in library
    params: List[Tuple[str, NativeType]]  # (name, type)
    return_type: NativeType
    is_unsafe: bool = False
    doc: str = ""
    library: str = "libvir_native"


@dataclass
class NativeStruct:
    """Represents a native struct to be bridged."""
    name: str
    c_name: str
    fields: List[Tuple[str, NativeType]]
    is_opaque: bool = False


@dataclass
class NativeLibrary:
    """Represents a native library to link."""
    name: str
    path: str
    is_framework: bool = False
    functions: List[NativeFunction] = field(default_factory=list)
    structs: List[NativeStruct] = field(default_factory=list)


class SwiftNativeBridge:
    """
    Generates Swift FFI bindings for native C/C++/Rust libraries.
    
    Usage:
        bridge = SwiftNativeBridge()
        bridge.add_library("libvir_math", "/path/to/libvir_math.a")
        bridge.add_function(NativeFunction(
            name="fast_dot_product",
            c_name="vir_math_dot_product",
            params=[("a", NativeType.POINTER), ("b", NativeType.POINTER), ("len", NativeType.INT64)],
            return_type=NativeType.FLOAT64
        ))
        swift_code = bridge.generate_bridge()
    """
    
    def __init__(self):
        self.libraries: Dict[str, NativeLibrary] = {}
        self.functions: List[NativeFunction] = []
        self.structs: List[NativeStruct] = []
        
        # Type mappings
        self._init_type_mappings()
        
    def _init_type_mappings(self):
        """Initialize C type → Swift type mappings."""
        self.c_to_swift: Dict[NativeType, str] = {
            NativeType.VOID: "Void",
            NativeType.INT8: "Int8",
            NativeType.INT16: "Int16",
            NativeType.INT32: "Int32",
            NativeType.INT64: "Int64",
            NativeType.UINT8: "UInt8",
            NativeType.UINT16: "UInt16",
            NativeType.UINT32: "UInt32",
            NativeType.UINT64: "UInt64",
            NativeType.FLOAT32: "Float",
            NativeType.FLOAT64: "Double",
            NativeType.BOOL: "Bool",
            NativeType.POINTER: "UnsafeMutableRawPointer",
            NativeType.CONST_POINTER: "UnsafeRawPointer",
            NativeType.STRING: "UnsafePointer<CChar>",
            NativeType.OPAQUE: "OpaquePointer",
        }
        
        self.swift_to_c_decl: Dict[NativeType, str] = {
            NativeType.VOID: "void",
            NativeType.INT8: "int8_t",
            NativeType.INT16: "int16_t",
            NativeType.INT32: "int32_t",
            NativeType.INT64: "int64_t",
            NativeType.UINT8: "uint8_t",
            NativeType.UINT16: "uint16_t",
            NativeType.UINT32: "uint32_t",
            NativeType.UINT64: "uint64_t",
            NativeType.FLOAT32: "float",
            NativeType.FLOAT64: "double",
            NativeType.BOOL: "bool",
            NativeType.POINTER: "void*",
            NativeType.CONST_POINTER: "const void*",
            NativeType.STRING: "const char*",
            NativeType.OPAQUE: "void*",
        }
        
    # ═══════════════════════════════════════════════════════════════════════════
    # REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_library(self, name: str, path: str, is_framework: bool = False):
        """Register a native library."""
        self.libraries[name] = NativeLibrary(
            name=name,
            path=path,
            is_framework=is_framework
        )
        
    def add_function(self, func: NativeFunction, library: str = None):
        """Register a native function."""
        self.functions.append(func)
        if library and library in self.libraries:
            self.libraries[library].functions.append(func)
            
    def add_struct(self, struct: NativeStruct, library: str = None):
        """Register a native struct."""
        self.structs.append(struct)
        if library and library in self.libraries:
            self.libraries[library].structs.append(struct)
            
    # ═══════════════════════════════════════════════════════════════════════════
    # CODE GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def generate_bridge(self) -> str:
        """Generate complete Swift bridge code."""
        sections = [
            self._generate_header(),
            self._generate_c_imports(),
            self._generate_struct_definitions(),
            self._generate_function_declarations(),
            self._generate_swift_wrappers(),
            self._generate_utility_functions(),
        ]
        return '\n\n'.join(filter(None, sections))
        
    def _generate_header(self) -> str:
        """Generate file header."""
        return '''\
// ═══════════════════════════════════════════════════════════════════════════════
// Vir Native Bridge — Auto-generated Swift FFI
// ═══════════════════════════════════════════════════════════════════════════════
// 
// This file bridges Vir code to native C/C++/Rust libraries.
// Do not edit manually — regenerate using `vir bridge`.
//
// Libraries:
''' + '\n'.join(f'//   - {lib.name}: {lib.path}' for lib in self.libraries.values()) + '''
// ═══════════════════════════════════════════════════════════════════════════════

import Foundation'''
        
    def _generate_c_imports(self) -> str:
        """Generate C header imports."""
        if not self.functions and not self.structs:
            return ""
            
        lines = [
            "// C Function Declarations",
            "#if canImport(Darwin)",
            "import Darwin",
            "#elseif canImport(Glibc)",
            "import Glibc",
            "#endif",
        ]
        
        # Generate @_silgen_name imports for each function
        for func in self.functions:
            c_decl = self._generate_c_declaration(func)
            lines.append(f"\n// {func.doc}" if func.doc else "")
            lines.append(c_decl)
            
        return '\n'.join(lines)
        
    def _generate_c_declaration(self, func: NativeFunction) -> str:
        """Generate C function declaration using @_silgen_name."""
        params_str = ", ".join(
            f"_ {name}: {self.c_to_swift[typ]}"
            for name, typ in func.params
        )
        
        return_str = self.c_to_swift[func.return_type]
        
        return f'''@_silgen_name("{func.c_name}")
func _native_{func.name}({params_str}) -> {return_str}'''

    def _generate_struct_definitions(self) -> str:
        """Generate Swift struct definitions for native structs."""
        if not self.structs:
            return ""
            
        lines = ["// Native Struct Definitions"]
        
        for struct in self.structs:
            if struct.is_opaque:
                lines.append(f"\ntypealias {struct.name} = OpaquePointer")
            else:
                lines.append(f"\nstruct {struct.name} {{")
                for fname, ftype in struct.fields:
                    lines.append(f"    var {fname}: {self.c_to_swift[ftype]}")
                lines.append("}")
                
        return '\n'.join(lines)
        
    def _generate_function_declarations(self) -> str:
        """Generate extern function declarations."""
        return ""  # Handled in _generate_c_imports
        
    def _generate_swift_wrappers(self) -> str:
        """Generate safe Swift wrapper functions."""
        if not self.functions:
            return ""
            
        lines = [
            "// ═══════════════════════════════════════════════════════════════════════════",
            "// Swift Wrapper Functions",
            "// ═══════════════════════════════════════════════════════════════════════════",
            "",
            "/// VirNative provides safe Swift wrappers for native functions.",
            "enum VirNative {",
        ]
        
        for func in self.functions:
            wrapper = self._generate_wrapper_function(func)
            lines.append(wrapper)
            
        lines.append("}")
        return '\n'.join(lines)
        
    def _generate_wrapper_function(self, func: NativeFunction) -> str:
        """Generate a safe Swift wrapper for a native function."""
        # Build parameter list with Swift-friendly types
        swift_params = []
        call_args = []
        
        for name, typ in func.params:
            swift_type = self._get_swift_friendly_type(typ)
            swift_params.append(f"{name}: {swift_type}")
            
            # Add conversion code if needed
            call_arg = self._convert_to_native(name, typ)
            call_args.append(call_arg)
            
        params_str = ", ".join(swift_params)
        call_str = ", ".join(call_args)
        return_type = self._get_swift_friendly_type(func.return_type)
        
        doc = f"    /// {func.doc}\n" if func.doc else ""
        
        return f'''{doc}    static func {func.name}({params_str}) -> {return_type} {{
        return _native_{func.name}({call_str})
    }}
'''
        
    def _get_swift_friendly_type(self, typ: NativeType) -> str:
        """Get a more Swift-friendly type for the public API."""
        # For most types, use the C type directly
        # But translate some for better ergonomics
        friendly = {
            NativeType.STRING: "String",
            NativeType.POINTER: "[UInt8]",
        }
        return friendly.get(typ, self.c_to_swift[typ])
        
    def _convert_to_native(self, name: str, typ: NativeType) -> str:
        """Generate conversion code from Swift type to native type."""
        if typ == NativeType.STRING:
            return f'{name}.withCString {{ $0 }}'
        return name
        
    def _generate_utility_functions(self) -> str:
        """Generate utility functions for memory management."""
        return '''\
// ═══════════════════════════════════════════════════════════════════════════════
// Memory Utilities
// ═══════════════════════════════════════════════════════════════════════════════

extension VirNative {
    /// Allocate memory for native operations
    static func allocate(bytes: Int) -> UnsafeMutableRawPointer {
        return UnsafeMutableRawPointer.allocate(byteCount: bytes, alignment: 8)
    }
    
    /// Deallocate memory
    static func deallocate(_ ptr: UnsafeMutableRawPointer) {
        ptr.deallocate()
    }
    
    /// Copy data to native buffer
    static func copyToNative<T>(_ array: [T], to ptr: UnsafeMutableRawPointer) {
        array.withUnsafeBytes { bytes in
            ptr.copyMemory(from: bytes.baseAddress!, byteCount: bytes.count)
        }
    }
    
    /// Copy data from native buffer
    static func copyFromNative<T>(_ ptr: UnsafeRawPointer, count: Int, as type: T.Type) -> [T] {
        let buffer = ptr.bindMemory(to: T.self, capacity: count)
        return Array(UnsafeBufferPointer(start: buffer, count: count))
    }
}
'''
        
    # ═══════════════════════════════════════════════════════════════════════════
    # BRIDGING HEADER GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def generate_bridging_header(self) -> str:
        """Generate a C bridging header for Xcode projects."""
        lines = [
            "// Vir Native Bridging Header",
            "// Auto-generated — do not edit manually",
            "",
            "#ifndef VIR_NATIVE_BRIDGE_H",
            "#define VIR_NATIVE_BRIDGE_H",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "",
        ]
        
        # Struct declarations
        for struct in self.structs:
            if not struct.is_opaque:
                lines.append(f"typedef struct {{")
                for fname, ftype in struct.fields:
                    lines.append(f"    {self.swift_to_c_decl[ftype]} {fname};")
                lines.append(f"}} {struct.c_name};")
                lines.append("")
                
        # Function declarations
        for func in self.functions:
            params = ", ".join(
                f"{self.swift_to_c_decl[typ]} {name}"
                for name, typ in func.params
            )
            ret = self.swift_to_c_decl[func.return_type]
            lines.append(f"extern {ret} {func.c_name}({params});")
            
        lines.extend([
            "",
            "#endif // VIR_NATIVE_BRIDGE_H",
        ])
        
        return '\n'.join(lines)
        
    # ═══════════════════════════════════════════════════════════════════════════
    # MODULE MAP GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def generate_module_map(self, module_name: str = "VirNativeCore") -> str:
        """Generate a module.modulemap for the native library."""
        umbrella_header = f"{module_name}.h"
        
        return f'''\
module {module_name} {{
    umbrella header "{umbrella_header}"
    
    export *
    module * {{ export * }}
}}
'''
        
    # ═══════════════════════════════════════════════════════════════════════════
    # FILE WRITING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def write_bridge(self, output_dir: str):
        """Write all bridge files to a directory."""
        os.makedirs(output_dir, exist_ok=True)
        
        # Swift bridge
        swift_path = os.path.join(output_dir, "VirNativeBridge.swift")
        with open(swift_path, 'w') as f:
            f.write(self.generate_bridge())
            
        # Bridging header
        header_path = os.path.join(output_dir, "VirNative-Bridging-Header.h")
        with open(header_path, 'w') as f:
            f.write(self.generate_bridging_header())
            
        # Module map
        modulemap_path = os.path.join(output_dir, "module.modulemap")
        with open(modulemap_path, 'w') as f:
            f.write(self.generate_module_map())
            
        return {
            'swift': swift_path,
            'header': header_path,
            'modulemap': modulemap_path,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-DEFINED NATIVE CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_vir_math_bridge() -> SwiftNativeBridge:
    """Create a bridge for the Vir math library."""
    bridge = SwiftNativeBridge()
    bridge.add_library("libvir_math", "libvir_math.a")
    
    # Vector operations
    bridge.add_function(NativeFunction(
        name="dot_product",
        c_name="vir_math_dot_product_f32",
        params=[
            ("a", NativeType.CONST_POINTER),
            ("b", NativeType.CONST_POINTER),
            ("len", NativeType.INT64)
        ],
        return_type=NativeType.FLOAT32,
        doc="Compute dot product of two float vectors"
    ), "libvir_math")
    
    bridge.add_function(NativeFunction(
        name="vec_add",
        c_name="vir_math_vec_add_f32",
        params=[
            ("a", NativeType.CONST_POINTER),
            ("b", NativeType.CONST_POINTER),
            ("out", NativeType.POINTER),
            ("len", NativeType.INT64)
        ],
        return_type=NativeType.VOID,
        doc="Add two float vectors element-wise"
    ), "libvir_math")
    
    bridge.add_function(NativeFunction(
        name="matrix_mul",
        c_name="vir_math_matmul_f32",
        params=[
            ("a", NativeType.CONST_POINTER),
            ("b", NativeType.CONST_POINTER),
            ("out", NativeType.POINTER),
            ("m", NativeType.INT64),
            ("n", NativeType.INT64),
            ("k", NativeType.INT64)
        ],
        return_type=NativeType.VOID,
        doc="Matrix multiplication: out = a @ b"
    ), "libvir_math")
    
    return bridge


def create_vir_simd_bridge() -> SwiftNativeBridge:
    """Create a bridge for SIMD operations."""
    bridge = SwiftNativeBridge()
    bridge.add_library("libvir_simd", "libvir_simd.a")
    
    bridge.add_function(NativeFunction(
        name="simd_sum",
        c_name="vir_simd_sum_f32",
        params=[
            ("data", NativeType.CONST_POINTER),
            ("len", NativeType.INT64)
        ],
        return_type=NativeType.FLOAT32,
        doc="SIMD-accelerated sum of float array"
    ), "libvir_simd")
    
    bridge.add_function(NativeFunction(
        name="simd_sqrt",
        c_name="vir_simd_sqrt_f32",
        params=[
            ("data", NativeType.CONST_POINTER),
            ("out", NativeType.POINTER),
            ("len", NativeType.INT64)
        ],
        return_type=NativeType.VOID,
        doc="SIMD-accelerated sqrt of float array"
    ), "libvir_simd")
    
    return bridge
