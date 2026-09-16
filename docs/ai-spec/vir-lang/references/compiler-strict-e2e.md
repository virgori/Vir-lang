# Compiler Strict E2E Contract

**Status:** normative implementation contract for Vir v2.0 / Compiler v3.1+

This document turns the existing language rules for numeric expressions,
casts, dictionaries, registers, and molds into mandatory end-to-end compiler
requirements.  A feature is **not implemented** until its strict source test
compiles to a native executable and that executable produces the specified
output.  Parsing or MIR-only acceptance is insufficient.

## 1. Scope and conformance

The contract covers these test groups:

- §4: primitive types and casts;
- §10: arithmetic, including scalar power;
- §16: register and mold bit layouts;
- §20: dictionary and map values.

Every implementation must preserve the source spelling shown here.  Test
normalization must never replace a normative result with raw IEEE-754 bits,
change an operator spelling, or remove a construct merely to make an
incomplete backend pass.  Such a mismatch is a compiler defect, not a test
defect.

The required verification path is:

1. Parse the strict `.vri` source without recovery diagnostics.
2. Resolve names and types, preserving all information required by lowering.
3. Emit executable native code for the selected target.
4. Execute it and compare stdout and process status exactly.
5. Run the corresponding `run_tests.sh` group in both `min` and full modes.

An implementation may add optimized lowering or alternate target backends,
but they must have the same observable behavior.

## 2. Scalar arithmetic

### 2.1 Negative integers

Unary `-` is a signed arithmetic operation.  `-7` evaluates to the signed
integer `-7`; it is not a parser-only token sequence and not an unsigned raw
word.  Arithmetic with a negative operand follows the normal signed behavior
of the selected integer type.

### 2.2 Scalar power `^`

`^` is scalar exponentiation.  It is accepted with no whitespace on either
side: `2^3` is canonical and must have exactly the same meaning as `2 ^ 3`.
It is right-associative: `2^3^2` means `2^(3^2)` and produces `512`.

For integer operands, the exponent must be a non-negative integer.  `x^0` is
`1`, including when `x` is zero.  Integer overflow follows the language's
chosen fixed-width wrapping policy; it must not silently become a float,
pointer, or an uninitialised register.  A negative integer exponent must be
rejected during semantic checking until a distinct floating-power contract is
specified.

`**` remains tensor matrix multiplication only; it must never be used as an
alternative spelling for scalar power.

### 2.3 Required §10 tests

Add and retain these native E2E cases (expected stdout shown):

```vir
# tests/strict_v2/power_no_space_e2e.vri
func main:
    print 2^3
    print 2^3^2
    print 9^0
end.
# EXPECT_START
# 8
# 512
# 1
# EXPECT_END
```

Also retain a compile-fail test for `2^-1`, with a stable diagnostic that
identifies an invalid negative integer exponent.  The test must not execute a
native binary after the diagnostic.

## 3. Float and integer conversion

### 3.1 Representation boundary

`float` is IEEE-754 binary64.  Its in-memory bit pattern is an implementation
detail.  `print`, comparisons, casts, calls, stores, and returns must observe
numeric float semantics, never expose the bit pattern in place of the numeric
value.

### 3.2 `int` / signed integer to `float`

`value as float` converts the numeric signed-integer value to binary64 using
the target IEEE-754 conversion instruction or an equivalent correctly-rounded
operation.  It is not a bit reinterpretation.  Values not exactly representable
in binary64 use IEEE-754 round-to-nearest, ties-to-even.

### 3.3 `float` to `int` / signed integer

`value as int` converts toward zero.  Thus `12.9 as int` is `12` and
`-12.9 as int` is `-12`.  The conversion is valid only for finite values in
the destination signed range.  NaN, either infinity, and an out-of-range value
must trap through the defined conversion-error path; they must not be
reinterpreted as an integer word, saturated silently, or invoke undefined
native behavior.

Conversions to fixed-width signed types additionally range-check their target
range.  Unsigned conversion is not implicitly selected by `as int`; when
introduced, it needs its own explicit signedness and range contract.

### 3.4 Compiler pipeline requirement

The parser must record the cast target type in the AST.  Lowering must retain
both source and destination numeric categories in MIR/LIR.  The backend must
emit a numeric conversion (not `Move`, `fmov`, or payload-copy semantics) and
must correctly spill a conversion result when its destination is not assigned
a physical register.

### 3.5 Required §4 tests

```vir
# tests/strict_v2/float_int_cast_e2e.vri
func main:
    var a: float = 42
    var b = 12.9 as int
    var c = -12.9 as int
    print a as int
    print b
    print c
end.
# EXPECT_START
# 42
# 12
# -12
# EXPECT_END
```

The suite must also include variable, call-return, array/dict-store, and
spill-pressure variants of both conversion directions.  It must include
compile/run failure coverage for NaN, infinity, and signed-range overflow once
those literals or constructors are exposed by the standard runtime.

## 4. Dictionary and map values

### 4.1 Observable dictionary contract

The literal `[key: value, ...]` constructs a dictionary.  `d[key]` retrieves
the value for an existing key and `d[key] = value` updates an existing entry or
inserts a new entry.  Updating an existing key does not change `len(d)`.
Inserting a new key increments `len(d)` by one.  Integer keys compare by
integer value; string keys compare by string contents, not pointer identity.

The current native layout is an implementation ABI:

```text
offset 0:  i64 logical length
offset 8:  i64 capacity
offset 16: entry 0 key (i64 word)
offset 24: entry 0 value (i64 word)
offset 32: entry 1 key
offset 40: entry 1 value
...
```

No generic array lowering may assume a dictionary payload is a contiguous
single-word element array.  Dictionary lookup/store must address key/value
pairs at `16 + index * 16` and must preserve values across loop blocks,
register allocation, and spills.  Capacity exhaustion must grow the table or
raise the documented dictionary-capacity error; it must never overwrite memory.

### 4.2 Required §20 tests

```vir
# tests/strict_v2/dict_int_update_e2e.vri
func main:
    var d = [1: 100, 2: 200, 3: 300]
    print d[1]
    print d[2]
    print d[3]
    d[2] = 250
    d[4] = 400
    print len(d)
    print d[2]
    print d[4]
end.
# EXPECT_START
# 100
# 200
# 300
# 4
# 250
# 400
# EXPECT_END
```

Add equivalent tests for string keys, lookup after multiple inserts, update
without length growth, and enough entries to exercise the capacity boundary.
Each test must run as a native executable; an AST/MIR snapshot is supplementary
only.

## 5. Register and mold layouts

### 5.1 Register

`register Name: BaseType` names explicitly-positioned bitfields.  A one-bit
field uses `NAME: bit`; a range `NAME: lo..hi` is inclusive.  Reading yields
the unsigned field value; assignment replaces only that field's bits, leaving
all non-overlapping fields unchanged.  A range must satisfy `0 <= lo <= hi <
bit_width(BaseType)`.

### 5.2 Mold

`mold Name: BaseType` names consecutively packed bitfields.  Each width form
`field: width` consumes `width` bits starting at the next free low-order bit.
Fields may be separated by commas or newlines, including mixed use on one
line.  The total width must not exceed `bit_width(BaseType)`.  A non-positive
width or overflow is a semantic diagnostic, never silently clamped or
truncated.

Mold must share the end-to-end behavior of register: declaration parsing,
symbol/type registration, construction from the base value, field insertion,
field extraction, nested expression use, local variable persistence, and
native code generation.  `end.` is required for both definitions.

### 5.3 Required §16 tests

```vir
# tests/strict_v2/mold_packed_e2e.vri
mold Pixel: u16
    r: 5, g: 6, b: 5
end.

func main:
    var px: Pixel = 0
    px.r = 31
    px.g = 42
    px.b = 7
    print px.r
    print px.g
    print px.b
end.
# EXPECT_START
# 31
# 42
# 7
# EXPECT_END
```

The group must include a newline-separated mold, a mixed comma/newline mold,
non-overlap preservation checks, maximum-width field checks, and compile-fail
cases for width zero, negative width, and total-width overflow.

## 6. Test registration and release gate

Every required E2E file above must be registered in the matching
`run_group_4`, `run_group_10`, `run_group_16`, or `run_group_20` branch of
`/Users/gengyang/Vir/run_tests.sh`; strict tests belong in both `min` and full
mode unless their stated purpose is exhaustive stress coverage.

Before promoting `bin/virc`, the release gate is:

```text
./run_tests.sh 4
./run_tests.sh 10
./run_tests.sh 16
./run_tests.sh 20
./run_tests.sh all
```

All required tests must pass with no compiler crash, native SIGSEGV, missing
output artifact, path-dependent runtime behavior, or expected-output rewrite.
Any failure is classified as either an unimplemented feature or a regression;
it may only be classified as a test defect with a demonstrated contradiction
against this contract or the base Vir v2.0 specification.
