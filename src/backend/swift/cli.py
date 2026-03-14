#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# Vir → Swift Build CLI
# ═══════════════════════════════════════════════════════════════════════════════
# 
# Command-line interface for building Vir projects to Swift/iOS/macOS apps.
#
# Usage:
#   vir build                    # Build current project
#   vir build src/main.vir       # Build specific file
#   vir build --target ios       # Build for iOS
#   vir build --release          # Release build
#   vir transpile src/           # Only transpile, don't compile
#
# Pipeline:
#   1. Scan .vir files in project
#   2. Transpile to .swift files
#   3. Generate native bridge if needed
#   4. Call swiftc / swift build
#   5. Output binary or .app bundle
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import glob
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from enum import Enum, auto
import json


class BuildTarget(Enum):
    """Build target platforms."""
    MACOS = "macos"
    IOS = "ios"
    IOS_SIMULATOR = "ios-simulator"
    WATCHOS = "watchos"
    TVOS = "tvos"


class BuildMode(Enum):
    """Build configuration."""
    DEBUG = "debug"
    RELEASE = "release"


@dataclass
class BuildConfig:
    """Build configuration settings."""
    target: BuildTarget = BuildTarget.MACOS
    mode: BuildMode = BuildMode.DEBUG
    output_dir: str = ".build"
    swift_output_dir: str = ".build/swift"
    product_name: str = "VirApp"
    min_version: str = "14.0"
    native_libs: List[str] = field(default_factory=list)
    swift_flags: List[str] = field(default_factory=list)
    verbose: bool = False
    

@dataclass
class BuildResult:
    """Result of a build operation."""
    success: bool
    output_path: Optional[str] = None
    swift_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: int = 0


class VirSwiftBuilder:
    """
    Main build orchestrator for Vir → Swift compilation.
    
    Usage:
        builder = VirSwiftBuilder()
        result = builder.build("src/main.vir", config)
    """
    
    def __init__(self):
        from .transpiler import VirToSwiftTranspiler
        from .bridge import SwiftNativeBridge
        
        self.transpiler = VirToSwiftTranspiler()
        self.bridge = SwiftNativeBridge()
        
    # ═══════════════════════════════════════════════════════════════════════════
    # BUILD COMMANDS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def build(self, source: str, config: BuildConfig = None) -> BuildResult:
        """
        Build a Vir project or file to native binary.
        
        Args:
            source: Path to .vir file or directory
            config: Build configuration
            
        Returns:
            BuildResult with output path and status
        """
        import time
        start = time.time()
        
        if config is None:
            config = BuildConfig()
            
        result = BuildResult(success=False)
        
        try:
            # Step 1: Collect .vir files
            vir_files = self._collect_vir_files(source)
            if not vir_files:
                result.errors.append(f"No .vir files found in {source}")
                return result
                
            if config.verbose:
                print(f"Found {len(vir_files)} Vir file(s)")
                
            # Step 2: Create output directory
            os.makedirs(config.swift_output_dir, exist_ok=True)
            
            # Step 3: Transpile each .vir file to .swift
            swift_files = []
            for vir_file in vir_files:
                swift_file = self._transpile_file(vir_file, config)
                if swift_file:
                    swift_files.append(swift_file)
                    result.swift_files.append(swift_file)
                else:
                    result.errors.append(f"Failed to transpile {vir_file}")
                    
            if not swift_files:
                result.errors.append("No Swift files generated")
                return result
                
            # Step 4: Generate native bridge if needed
            if config.native_libs:
                bridge_file = self._generate_native_bridge(config)
                if bridge_file:
                    swift_files.append(bridge_file)
                    
            # Step 5: Compile with swiftc
            output_path = self._compile_swift(swift_files, config)
            
            if output_path:
                result.success = True
                result.output_path = output_path
            else:
                result.errors.append("Swift compilation failed")
                
        except Exception as e:
            result.errors.append(str(e))
            
        result.duration_ms = int((time.time() - start) * 1000)
        return result
        
    def transpile_only(self, source: str, config: BuildConfig = None) -> BuildResult:
        """
        Only transpile .vir to .swift without compiling.
        
        Use this when you want to manually compile or debug the Swift code.
        """
        if config is None:
            config = BuildConfig()
            
        result = BuildResult(success=False)
        
        vir_files = self._collect_vir_files(source)
        if not vir_files:
            result.errors.append(f"No .vir files found in {source}")
            return result
            
        os.makedirs(config.swift_output_dir, exist_ok=True)
        
        for vir_file in vir_files:
            swift_file = self._transpile_file(vir_file, config)
            if swift_file:
                result.swift_files.append(swift_file)
                
        result.success = len(result.swift_files) > 0
        return result
        
    # ═══════════════════════════════════════════════════════════════════════════
    # INTERNAL METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _collect_vir_files(self, source: str) -> List[str]:
        """Collect all .vir files from source path."""
        if os.path.isfile(source):
            return [source] if source.endswith('.vir') else []
            
        if os.path.isdir(source):
            return glob.glob(os.path.join(source, "**/*.vir"), recursive=True)
            
        # Glob pattern
        return glob.glob(source)
        
    def _transpile_file(self, vir_path: str, config: BuildConfig) -> Optional[str]:
        """Transpile a single .vir file to .swift."""
        try:
            # Read Vir source
            with open(vir_path, 'r', encoding='utf-8') as f:
                vir_source = f.read()
                
            # Transpile
            swift_code = self.transpiler.transpile(vir_source)
            
            # Determine output path
            rel_path = os.path.basename(vir_path)
            swift_name = rel_path.replace('.vir', '.swift')
            swift_path = os.path.join(config.swift_output_dir, swift_name)
            
            # Write Swift file
            with open(swift_path, 'w', encoding='utf-8') as f:
                f.write(swift_code)
                
            if config.verbose:
                print(f"  {vir_path} → {swift_path}")
                
            return swift_path
            
        except Exception as e:
            print(f"Error transpiling {vir_path}: {e}", file=sys.stderr)
            return None
            
    def _generate_native_bridge(self, config: BuildConfig) -> Optional[str]:
        """Generate Swift bridge for native libraries."""
        for lib_path in config.native_libs:
            lib_name = os.path.splitext(os.path.basename(lib_path))[0]
            self.bridge.add_library(lib_name, lib_path)
            
        bridge_code = self.bridge.generate_bridge()
        bridge_path = os.path.join(config.swift_output_dir, "VirNativeBridge.swift")
        
        with open(bridge_path, 'w') as f:
            f.write(bridge_code)
            
        return bridge_path
        
    def _compile_swift(self, swift_files: List[str], config: BuildConfig) -> Optional[str]:
        """Compile Swift files using swiftc."""
        output_name = config.product_name
        output_path = os.path.join(config.output_dir, output_name)
        
        cmd = ["swiftc"]
        
        # Optimization level
        if config.mode == BuildMode.RELEASE:
            cmd.extend(["-O", "-whole-module-optimization"])
        else:
            cmd.extend(["-Onone", "-g"])
            
        # Target platform
        target_map = {
            BuildTarget.MACOS: f"-target arm64-apple-macosx{config.min_version}",
            BuildTarget.IOS: f"-target arm64-apple-ios{config.min_version}",
            BuildTarget.IOS_SIMULATOR: f"-target arm64-apple-ios{config.min_version}-simulator",
        }
        
        if config.target in target_map:
            cmd.append(target_map[config.target])
            
        # Output
        cmd.extend(["-o", output_path])
        
        # Native libraries
        for lib in config.native_libs:
            if lib.endswith('.a'):
                cmd.extend(["-L", os.path.dirname(lib)])
                lib_name = os.path.basename(lib)[3:-2]  # libfoo.a → foo
                cmd.extend(["-l", lib_name])
            elif lib.endswith('.framework'):
                cmd.extend(["-F", os.path.dirname(lib)])
                fw_name = os.path.basename(lib)[:-10]  # Foo.framework → Foo
                cmd.extend(["-framework", fw_name])
                
        # Additional flags
        cmd.extend(config.swift_flags)
        
        # Source files
        cmd.extend(swift_files)
        
        if config.verbose:
            print(f"$ {' '.join(cmd)}")
            
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Swift compilation failed:\n{result.stderr}", file=sys.stderr)
                return None
                
            return output_path
            
        except FileNotFoundError:
            print("Error: swiftc not found. Please install Xcode or Swift toolchain.", 
                  file=sys.stderr)
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def create_argument_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="vir",
        description="Vir Language Compiler — Build native apps from Vir source"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # vir build
    build_parser = subparsers.add_parser("build", help="Build Vir project to native binary")
    build_parser.add_argument("source", nargs="?", default=".", 
                              help="Source file or directory (default: current dir)")
    build_parser.add_argument("-o", "--output", help="Output directory")
    build_parser.add_argument("--target", choices=["macos", "ios", "ios-simulator"],
                              default="macos", help="Target platform")
    build_parser.add_argument("--release", action="store_true", help="Release build")
    build_parser.add_argument("--native-lib", action="append", dest="native_libs",
                              default=[], help="Native library to link")
    build_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    # vir transpile
    transpile_parser = subparsers.add_parser("transpile", 
                                              help="Transpile .vir to .swift only")
    transpile_parser.add_argument("source", nargs="?", default=".",
                                   help="Source file or directory")
    transpile_parser.add_argument("-o", "--output", help="Output directory for Swift files")
    transpile_parser.add_argument("-v", "--verbose", action="store_true")
    
    # vir init
    init_parser = subparsers.add_parser("init", help="Initialize new Vir project")
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument("--template", choices=["app", "lib", "swiftui"],
                             default="app", help="Project template")
    
    # vir bridge
    bridge_parser = subparsers.add_parser("bridge", 
                                           help="Generate native bridge from header file")
    bridge_parser.add_argument("header", help="C header file path")
    bridge_parser.add_argument("-o", "--output", help="Output Swift file")
    
    return parser


def swift_build_command(args: List[str] = None):
    """
    Main entry point for CLI.
    
    Usage from code:
        swift_build_command(["build", "src/main.vir", "--release"])
    """
    parser = create_argument_parser()
    parsed = parser.parse_args(args)
    
    if parsed.command is None:
        parser.print_help()
        return 1
        
    builder = VirSwiftBuilder()
    
    if parsed.command == "build":
        config = BuildConfig(
            target=BuildTarget(parsed.target),
            mode=BuildMode.RELEASE if parsed.release else BuildMode.DEBUG,
            output_dir=parsed.output or ".build",
            swift_output_dir=os.path.join(parsed.output or ".build", "swift"),
            native_libs=parsed.native_libs or [],
            verbose=parsed.verbose,
        )
        
        result = builder.build(parsed.source, config)
        
        if result.success:
            print(f"✓ Build successful: {result.output_path}")
            print(f"  Time: {result.duration_ms}ms")
            return 0
        else:
            print("✗ Build failed:")
            for err in result.errors:
                print(f"  - {err}")
            return 1
            
    elif parsed.command == "transpile":
        config = BuildConfig(
            swift_output_dir=parsed.output or ".build/swift",
            verbose=parsed.verbose,
        )
        
        result = builder.transpile_only(parsed.source, config)
        
        if result.success:
            print(f"✓ Transpiled {len(result.swift_files)} file(s):")
            for sf in result.swift_files:
                print(f"  - {sf}")
            return 0
        else:
            print("✗ Transpilation failed")
            return 1
            
    elif parsed.command == "init":
        return init_project(parsed.name, parsed.template)
        
    elif parsed.command == "bridge":
        return generate_bridge_from_header(parsed.header, parsed.output)
        
    return 0


def init_project(name: str, template: str) -> int:
    """Initialize a new Vir project."""
    os.makedirs(name, exist_ok=True)
    
    # Create main.vir
    main_content = {
        "app": '''\
# {name} — Vir Application
# Generated by `vir init`

import Foundation

func main() -> i32
    print("Hello from {name}!")
    out 0
end
''',
        "swiftui": '''\
# {name} — Vir SwiftUI App
# Generated by `vir init`

import SwiftUI

entity ContentView
    # SwiftUI body would be generated here
end

func main() -> i32
    # SwiftUI app entry point
    out 0
end
''',
        "lib": '''\
# {name} — Vir Library
# Generated by `vir init`

export func hello(name: String) -> String
    out str_cat("Hello, ", name)
end
'''
    }
    
    main_path = os.path.join(name, "src", "main.vir")
    os.makedirs(os.path.dirname(main_path), exist_ok=True)
    
    with open(main_path, 'w') as f:
        f.write(main_content.get(template, main_content["app"]).format(name=name))
        
    # Create vir.json config
    config = {
        "name": name,
        "version": "0.1.0",
        "target": "macos",
        "entry": "src/main.vir",
        "native_libs": []
    }
    
    with open(os.path.join(name, "vir.json"), 'w') as f:
        json.dump(config, f, indent=2)
        
    print(f"✓ Created Vir project: {name}/")
    print(f"  - src/main.vir")
    print(f"  - vir.json")
    print(f"\nTo build: cd {name} && vir build")
    
    return 0


def generate_bridge_from_header(header_path: str, output_path: str = None) -> int:
    """Generate Swift bridge from C header file."""
    from .bridge import SwiftNativeBridge, NativeFunction, NativeType
    
    # TODO: Parse C header and generate bridge
    # For now, create a template
    
    bridge = SwiftNativeBridge()
    swift_code = bridge.generate_bridge()
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(swift_code)
        print(f"✓ Generated bridge: {output_path}")
    else:
        print(swift_code)
        
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# SCRIPT ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(swift_build_command())
