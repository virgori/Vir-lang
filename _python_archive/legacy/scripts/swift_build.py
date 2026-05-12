#!/usr/bin/env python3
"""
Vir → Swift Build Script

Entry point for transpiling Vir to Swift and building native apps.

Usage:
    python scripts/swift_build.py build src/main.vir
    python scripts/swift_build.py transpile src/
    python scripts/swift_build.py init MyApp --template swiftui
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from backend.swift.cli import swift_build_command

if __name__ == "__main__":
    sys.exit(swift_build_command())
