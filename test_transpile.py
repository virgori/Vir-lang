#!/usr/bin/env python3
"""Quick test for str_cat transpilation."""

import sys
sys.path.insert(0, '/Users/gengyang/Desktop/AI/Vir/src')

from backend.swift.transpiler import VirToSwiftTranspiler

vir_code = '''
func greet(name: String) -> String
    var greeting = str_cat("Hello, ", name)
    out str_cat(greeting, "!")
end
'''

t = VirToSwiftTranspiler()
swift_code = t.transpile(vir_code)
print(swift_code)
