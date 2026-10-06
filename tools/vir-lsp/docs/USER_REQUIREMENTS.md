# Vir Language Server Architecture

## 1. Mục tiêu

`vir-lsp` phải dùng chung semantic core với compiler Vir.

LSP không được chỉ hiểu:

- token
- syntax
- symbol name
- type

mà phải hiểu cả:

- vòng đời biến
- ownership
- move
- borrow
- mutable/shared borrow
- arena/sub-arena
- lifetime boundary
- scope
- include/import
- export/public visibility
- module dependency
- lời gọi hàm
- symbol activation
- value flow
- error provenance

Kiến trúc tổng:

```text
                    Vir Source
                        │
                        ▼
               Incremental Source DB
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
        Incremental Lexer     Dependency Scanner
              │                    │
              ▼                    ▼
        Recoverable Parser     Module Graph
              │                    │
              └─────────┬──────────┘
                        ▼
                       AST
                        │
                        ▼
               Semantic Analysis
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
     Symbol DB       Type DB      Lifetime DB
         │              │              │
         ├──────────────┼──────────────┤
         ▼              ▼              ▼
   Reference DB     Call Graph     Borrow Graph
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                  Analysis Engine
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
     virc            vir-lsp        Vir tooling
```

Nguyên tắc:

```text
compiler semantics = LSP semantics
```

Không tồn tại type checker riêng cho editor.

---

# 2. Các database cốt lõi

## 2.1 Source Database

Quản lý trạng thái hiện tại của từng file.

```text
SourceFile {
    fileId
    uri
    version
    text
    lineMap
    tokenTree
    syntaxTree
}
```

Phải hỗ trợ incremental update:

```text
edit
 ↓
affected range
 ↓
affected tokens
 ↓
affected syntax nodes
```

Không parse lại toàn bộ workspace sau mỗi ký tự.

---

# 3. Symbol Database

Mọi declaration phải được cấp `SymbolId` ổn định.

```text
Symbol {
    id
    name
    kind

    declaration
    definition

    module
    scope

    type
    visibility

    exported
    imported

    references[]
    reads[]
    writes[]
    calls[]
}
```

`kind`:

```text
module
namespace
entity
type
function
method
parameter
variable
constant
field
enum
generic
```

Symbol DB là nguồn dữ liệu cho:

- hover
- completion
- go to definition
- find references
- rename
- semantic highlighting
- call hierarchy
- symbol activation

---

# 4. Lifetime Database

Đây là thành phần đặc trưng của Vir.

Compiler đã hiểu lifetime thì LSP phải expose nó trực tiếp.

Mỗi variable:

```text
LifetimeInfo {
    symbolId

    declaration
    initialization

    lifetimeStart
    lifetimeEnd

    owner
    arena

    state

    moves[]
    borrows[]
    mutations[]
    reads[]

    invalidation
}
```

`state`:

```text
declared
uninitialized
initialized
active

borrowed_shared
borrowed_mut

moved
consumed

invalidated
out_of_scope
freed
```

Ví dụ:

```vir
var user = User(name: "Vir")

inspect(&user)

consume(user)

print(user.name)
```

LSP phải hiểu:

```text
user
│
├─ declared
├─ initialized
├─ active
├─ shared borrow
├─ active
├─ moved
└─ invalid use
```

Editor có thể highlight:

```text
user                    ACTIVE

inspect(&user)
         └──── borrowed

consume(user)
        └── move boundary

print(user.name)
      └── invalid after move
```

Hover sau `consume`:

```text
user: User

State: moved
Moved at: main.vri:14:13
Declared at: main.vri:8:5

[E4xxx] value used after move
```

---

# 5. Borrow Graph

LSP cần một graph riêng cho ownership/borrow.

```text
BorrowGraph {
    owner SymbolId
        │
        ├── SharedBorrow
        │      ├── borrower
        │      ├── start
        │      └── end
        │
        └── MutableBorrow
               ├── borrower
               ├── start
               └── end
}
```

Ví dụ:

```vir
var x = Box(...)

var a = &x
var b = &x

mutate(&mut x)
```

LSP biết:

```text
x
├── shared borrow a ────────┐
├── shared borrow b ────────┤ conflict
└── mutable borrow requested┘
```

Diagnostic không chỉ nói:

```text
cannot mutably borrow x
```

mà nên gửi `relatedInformation`:

```text
Mutable borrow conflicts with active shared borrows.

Borrow #1 started here
Borrow #2 started here
Mutable borrow requested here
```

---

# 6. Arena / Sub-arena Awareness

Vir có arena và sub-arena nên LSP phải hiểu memory region.

```text
ArenaInfo {
    arenaId

    parentArena
    children[]

    creation
    destruction

    allocations[]
}
```

Value:

```text
ValueRegion {
    symbolId
    arenaId
    lifetime
}
```

Ví dụ:

```text
Arena A
│
├─ user
├─ buffer
│
└─ SubArena B
   ├─ temp
   └─ result
```

LSP phải phát hiện:

```text
value escapes arena lifetime
```

Ví dụ:

```vir
func make() -> User:
    arena temp

    var user = User(...)
    return user
end
```

nếu `user` thuộc arena sẽ chết khi `make()` kết thúc:

```text
[E4xxx] value escapes arena

`user` belongs to `temp`
`temp` is released here
returned reference would outlive its arena
```

Đây nên là first-class LSP diagnostic, không phải chỉ compiler build mới báo.

---

# 7. Lifetime Visualization

Vir LSP nên hỗ trợ một extension riêng ngoài LSP chuẩn:

```text
vir/lifetime
```

Input:

```text
document
position
```

Output:

```text
symbol
states[]
transitions[]
borrowRanges[]
moveRanges[]
arena
```

Editor có thể vẽ:

```text
ACTIVE ───────── BORROWED ───────── ACTIVE ───── MOVED
   ▲                   ▲                         ▲
 declaration       inspect(&x)               consume(x)
```

Đây có thể trở thành một tính năng đặc trưng của Vir.

---

# 8. Syntax Diagnostics

Parser phải recovery được khi code chưa hoàn chỉnh.

Ví dụ user đang gõ:

```vir
func parse(
```

LSP không được mất toàn bộ syntax tree.

Parser tạo:

```text
FunctionDecl
├─ name: parse
├─ (
└─ MissingParameterList
```

Diagnostics:

```text
Expected parameter or `)`
```

Nhưng các phần còn lại của file vẫn usable.

Phải phát hiện:

- unexpected token
- missing token
- malformed declaration
- unclosed block
- invalid expression
- invalid generic syntax
- invalid type syntax
- duplicate modifier
- misplaced keyword

---

# 9. Declaration Diagnostics

Semantic layer phải kiểm tra:

```text
duplicate symbol
undefined symbol
shadowing
invalid declaration
invalid type declaration
invalid visibility
invalid generic
invalid overload
invalid field
invalid method receiver
```

Ví dụ:

```vir
var x = 1
var x = 2
```

LSP:

```text
[E2xxx] duplicate declaration `x`

First declared here.
```

---

# 10. Include / Import Analysis

Vir LSP phải có `Module Graph`.

```text
ModuleGraph {
    modules[]
    includes[]
    imports[]
    exports[]
}
```

Edge:

```text
A ─include──▶ B
A ─import───▶ C
```

LSP phải kiểm tra:

- module không tồn tại
- include path không tồn tại
- circular dependency
- duplicate include
- duplicate import
- import không dùng
- symbol không tồn tại trong module
- symbol không được export
- module visibility

Ví dụ:

```vir
include crypto
```

nhưng không tồn tại:

```text
[E3xxx] module `crypto` not found
```

Code action:

```text
Create module
Search available modules
```

---

# 11. Missing Import

Ví dụ user viết:

```vir
var users = Vec of (User)
```

nhưng `Vec` chưa được import/include.

LSP không nên chỉ báo:

```text
undefined symbol Vec
```

Mà phải tìm Symbol Index:

```text
Vec → module vec
```

Diagnostic:

```text
`Vec` is not in scope.
```

Code Action:

```text
Import `Vec`
Include `vec`
```

Nếu Vir convention là:

```vir
include vec
```

thì Quick Fix tự thêm:

```vir
include vec
```

---

# 12. Imported nhưng Symbol chưa Export

Ví dụ:

```vir
include foo

foo.secret()
```

`secret()` tồn tại nhưng không public/export.

LSP phải phân biệt:

```text
symbol not found
```

với:

```text
symbol exists but is not exported
```

Diagnostic:

```text
[E3xxx] `secret` is not exported by module `foo`

Declared in:
foo/internal.vri

Visibility:
module-private
```

Nếu source cùng workspace và user có quyền sửa:

Code Actions:

```text
Export `secret`
Use public alternative
Open declaration
```

Đây tốt hơn nhiều so với báo `undefined symbol`.

---

# 13. Import chưa được sử dụng

Ví dụ:

```vir
include crypto
include json
```

nhưng chỉ `json` được gọi.

Semantic token:

```text
crypto → inactive
json   → active
```

Diagnostic nhẹ:

```text
Unused include `crypto`
```

Quick fix:

```text
Remove unused include
```

---

# 14. Function Activation

Vir LSP nên hiểu function nào thực sự được gọi.

Mỗi function:

```text
FunctionUsage {
    symbolId

    declared
    exported

    directlyCalled
    indirectlyReachable

    callers[]
    callees[]

    entryReachable
}
```

Tạo `Call Graph`:

```text
main
├── server.start
│   ├── socket.open
│   └── worker.run
│
└── config.load
```

Function chưa có caller:

```text
unused
```

Function reachable từ entrypoint:

```text
active
```

Function chỉ export:

```text
public-unreferenced
```

Không được coi public API là dead code chỉ vì workspace hiện tại chưa gọi nó.

---

# 15. Active / Inactive Function Highlighting

Semantic modifiers riêng:

```text
vir.active
vir.inactive
vir.reachable
vir.exported
```

Ví dụ:

```vir
func parse():      // active
end

func oldParser():  // inactive
end
```

Editor có thể giảm opacity `oldParser()`.

Call:

```vir
parse()
```

có thể highlight giống definition đang active.

---

# 16. Call Hierarchy

LSP chuẩn hỗ trợ:

```text
incomingCalls
outgoingCalls
```

Vir phải triển khai đầy đủ.

Ví dụ hover/call hierarchy:

```text
http.serve
│
├─ called by:
│  ├─ main
│  └─ testServer
│
└─ calls:
   ├─ tcp.listen
   ├─ worker.start
   └─ router.dispatch
```

---

# 17. Value Access — Get / Read / Write

LSP phải phân biệt cách variable được sử dụng.

Không gom tất cả vào `references`.

```text
ReferenceKind {
    declaration
    read
    write
    readWrite

    borrow
    mutableBorrow

    move
    consume

    call
}
```

Ví dụ:

```vir
var count = 0

print(count)
count = 5
count += 1
```

LSP hiểu:

```text
count declaration
count read
count write
count read/write
```

Find References UI có thể filter:

```text
All
Reads
Writes
Borrows
Moves
```

---

# 18. Shared Value / Shared Borrow

Nếu Vir hỗ trợ share/shared references, phải thể hiện rõ:

```text
OwnershipKind {
    owned
    borrowed
    shared
    mutableBorrow
}
```

Hover:

```text
buffer: Buffer

Ownership: owned
Arena: requestArena
Shared borrows: 2
Mutable borrow: none
```

Hoặc:

```text
user: &User

Ownership: shared borrow
Owner: userStore
Lifetime: scope 51
```

---

# 19. Value Flow

Vir LSP nên có:

```text
vir/valueFlow
```

Ví dụ:

```vir
var a = getUser()
var b = a
save(b)
```

Graph:

```text
getUser()
   │
   ▼
   a
   │ move
   ▼
   b
   │ consume
   ▼
 save()
```

Nếu copy:

```text
a
├─copy→ b
└─active
```

Nếu move:

```text
a
└─move→ b

a = moved
```

Đây cực kỳ hữu ích cho ngôn ngữ có ownership.

---

# 20. Scope Graph

```text
Scope {
    id
    parent

    symbols[]
    children[]

    start
    end
}
```

Cho phép LSP hiểu:

```text
global
 └─ module
     └─ function
         ├─ parameter
         └─ block
             └─ local
```

Dùng cho:

- completion
- shadowing
- lifetime
- rename
- references

---

# 21. Type System Integration

Type database:

```text
TypeDB {
    primitive
    entity
    generic
    function
    reference
    tensor
    SIMD
    inferred
}
```

Không stringify type rồi so sánh string.

Mọi type có:

```text
TypeId
```

Ví dụ:

```text
Vec of (User)
```

được biểu diễn:

```text
GenericType {
    base = Vec
    args = [User]
}
```

---

# 22. Hover

Hover phải giàu semantic information.

Variable:

```text
user: User

Mutable
Owned

State: active
Arena: request
Lifetime: main:14 → main:42

Reads: 4
Writes: 1
Borrows: 2
```

Function:

```text
http.get(url: string) -> Result of (Response)

Module: http
Visibility: public

Called by: 7 functions
Calls: tcp.connect, io.read

Documentation...
```

Module:

```text
json

Included by 13 modules
Exports 24 symbols
```

---

# 23. Completion

Completion phải context-aware.

Sau:

```vir
user.
```

chỉ trả:

```text
fields
methods
extensions
```

Sau:

```vir
include 
```

trả module.

Sau:

```vir
Result of (
```

trả type candidates.

Sau:

```vir
return
```

rank expression compatible với return type trước.

---

# 24. Completion Ranking

Ưu tiên:

```text
1 local variables
2 parameters
3 object members
4 same module
5 imported symbols
6 dependency symbols
7 auto-import candidates
8 workspace symbols
```

Sau đó fuzzy rank.

---

# 25. Signature Help

Ví dụ:

```vir
router.add(
```

hiện:

```text
router.add(
    method: Method,
    path: string,
    handler: Handler
)
```

Highlight parameter hiện tại.

Generic cũng phải hiểu:

```text
Map of (K, V)
```

---

# 26. Go To Definition

Bắt buộc:

```text
variable → declaration
call → function
method → method
type → type declaration
field → entity field
module → module file
include → module
```

---

# 27. Go To Type Definition

Từ:

```vir
var user: User
```

jump tới:

```vir
entity User:
```

---

# 28. Find References

Không search text.

Dựa trên `SymbolId`.

Phân loại:

```text
Declaration
Read
Write
Borrow
Move
Call
Type reference
Export
Import
```

---

# 29. Rename

Rename phải semantic.

Không thay những identifier trùng tên nhưng khác scope.

Ví dụ:

```text
main.x
foo.x
User.x
```

là ba symbol khác nhau.

Rename module phải cập nhật:

```text
include
import
qualified symbol references
```

---

# 30. Semantic Tokens

Vir nên hỗ trợ semantic token đầy đủ.

Token types:

```text
namespace
module
type
entity
struct
enum
function
method
variable
parameter
property
keyword
number
string
operator
comment
```

Vir modifiers:

```text
declaration
definition
readonly
mutable
public
private

active
inactive

borrowed
shared
moved
consumed

deprecated
unused

arenaOwned
subArenaOwned
```

---

# 31. Inlay Hints

Ví dụ:

```vir
var x = load()
```

hiện:

```text
var x: Result of (Data) = load()
```

Function arguments:

```vir
connect(host: "localhost", port: 8080)
```

Lifetime/ownership hint tùy chọn:

```text
user   owned · arena=request
ref    &shared · owner=user
```

Không nên bật quá nhiều mặc định.

---

# 32. Code Actions

Phải hỗ trợ:

```text
Add missing include
Remove unused include
Export symbol
Import symbol

Create missing function
Create missing variable
Create missing module

Change type
Add explicit type

Clone/copy value
Move value
Shorten borrow

Fix visibility
```

Borrow-specific quick fix rất đáng giá.

Ví dụ:

```text
Cannot mutate `x` while shared borrow is active.
```

Code action:

```text
End borrow before mutation
Move mutation below borrow scope
```

Nếu compiler đủ chắc chắn mới cung cấp automatic edit.

---

# 33. Diagnostics Architecture

Diagnostic phải mang code ổn định:

```text
E1xxx syntax
E2xxx declaration/name
E3xxx module/import/export
E4xxx ownership/borrow/lifetime
E5xxx type
E6xxx control flow
E7xxx arena/memory
```

Ví dụ:

```text
E4102
Use after move
```

LSP trả:

```text
code
severity
range
message
relatedInformation[]
data
```

`data` có thể chứa:

```text
symbolId
moveSite
borrowId
arenaId
```

để Code Action xử lý.

---

# 34. Root-cause Diagnostics

Không spam cascading errors.

Ví dụ:

```vir
unknown.foo.bar()
```

Root:

```text
unknown is undefined
```

Không cần tiếp tục:

```text
cannot resolve foo
cannot infer foo
cannot resolve bar
cannot infer bar
```

Semantic engine cần:

```text
ErrorType
UnknownSymbolType
PoisonedExpression
```

để suppress downstream diagnostics.

---

# 35. Document Symbols

Outline:

```text
module
├─ entity User
│   ├─ id
│   └─ name
│
├─ func createUser
├─ func deleteUser
└─ func main
```

---

# 36. Workspace Symbols

Search toàn project:

```text
User
user.parse
http.serve
Buffer
```

Phải sử dụng persistent index nếu workspace lớn.

---

# 37. Folding Range

Hỗ trợ:

```text
function
entity
if
loop
match
comment block
banner
module docs
```

---

# 38. Selection Range

Editor mở rộng selection theo syntax tree:

```text
identifier
→ expression
→ statement
→ block
→ function
→ module
```

---

# 39. Document Highlight

Click symbol:

```text
declaration
reads
writes
moves
borrows
```

nên dùng highlight type khác nhau nếu client hỗ trợ.

---

# 40. Formatting

Formatter nên dùng AST, không regex.

```text
virfmt
```

có thể expose qua:

```text
textDocument/formatting
textDocument/rangeFormatting
```

---

# 41. Code Lens

Vir đặc biệt phù hợp với Code Lens.

Trên function:

```text
7 callers · 4 callees · active
```

Trên public API:

```text
exported · referenced by 12 modules
```

Trên variable:

```text
4 reads · 2 writes · 1 move
```

Nên configurable vì Code Lens có thể làm UI nặng.

---

# 42. Arena Lens

Vir-specific:

```text
requestArena
12 allocations · 3 sub-arenas · lifetime 4.3 KB static estimate
```

Hoặc:

```text
tempArena
released at line 92
```

Không cần memory-size nếu compiler chưa đủ dữ liệu chính xác.

---

# 43. Borrow Lens

Tại declaration:

```text
2 shared borrows · 0 mutable borrows · moved at line 44
```

Editor click để xem borrow graph.

---

# 44. Call Graph + Reachability

Entry points:

```text
main
tests
exported ABI
callbacks
```

Graph engine đánh dấu:

```text
reachable
unreachable
conditionally reachable
public root
```

Không được đánh dấu function exported là dead chỉ vì không có local caller.

---

# 45. Dead Symbol Detection

Có thể phát hiện:

```text
unused local
unused private function
unused private type
unused import
unused parameter
```

Nhưng:

```text
public/exported
FFI
entry point
reflection-visible
```

không được tự coi là dead.

---

# 46. Dependency Graph

LSP giữ graph:

```text
module
   ↓
imports/includes
   ↓
public signatures
   ↓
consumers
```

Khi sửa local implementation:

```text
invalidate function only
```

Khi sửa public signature:

```text
invalidate dependent modules
```

Đây là nền tảng cho incremental analysis.

---

# 47. Incremental Query Engine

Mỗi semantic query:

```text
typeOf(node)
resolveSymbol(node)
references(symbol)
lifetime(symbol)
borrowState(symbol, position)
moduleExports(module)
callers(function)
```

được memoize.

Dependency:

```text
query A
  depends on B
  depends on C
```

Khi source đổi chỉ invalidate affected queries.

Không chạy toàn bộ compiler pipeline.

---

# 48. Fast Path

Các interaction phải ưu tiên latency:

```text
completion
hover
goto
signature help
semantic token visible range
```

chỉ cần:

```text
parse
scope
name resolution
local type information
```

---

# 49. Deep Path

Sau debounce/save:

```text
full type checking
borrow checking
arena escape analysis
control flow
unused analysis
call reachability
```

Diagnostics cập nhật sau.

---

# 50. Cancellation

LSP request phải cancellable.

Ví dụ:

```text
completion at position A
```

user tiếp tục gõ position B:

```text
cancel A
compute B
```

Không để stale work chiếm CPU.

---

# 51. Versioned Results

Mọi analysis gắn:

```text
fileVersion
```

Không publish diagnostic của version 52 lên file đang version 57.

---

# 52. Broken Code Tolerance

Đây là yêu cầu bắt buộc.

Editor phần lớn thời gian chứa code chưa hoàn chỉnh.

Ví dụ:

```vir
func foo(a:
```

LSP vẫn phải giữ:

```text
module
foo declaration
scope
earlier functions
imports
symbols
```

Không được “analysis failed”.

---

# 53. Crash Isolation

Một function invalid không làm toàn workspace mất semantic data.

```text
file
 ├─ func good1 → analyzed
 ├─ func broken → poisoned
 └─ func good2 → analyzed
```

---

# 54. Mandatory Standard LSP Features

Vir LSP ít nhất phải có:

```text
initialize
shutdown

textDocument/didOpen
textDocument/didChange
textDocument/didClose
textDocument/didSave

publishDiagnostics

completion
completion resolve

hover

signatureHelp

definition
declaration
typeDefinition
implementation

references

documentHighlight

documentSymbol
workspace/symbol

rename
prepareRename

codeAction

semanticTokens

inlayHint

callHierarchy

foldingRange
selectionRange

formatting
rangeFormatting
```

Nên có:

```text
workspace diagnostics
workspace folders
file operations
linked editing
code lens
```

---

# 55. Vir Custom Protocol Extensions

Các tính năng Vir-specific nên đặt riêng:

```text
vir/lifetime
vir/borrowGraph
vir/valueFlow
vir/arenaGraph
vir/symbolState
vir/moduleGraph
vir/callGraph
```

Ví dụ:

```text
vir/symbolState
```

trả:

```text
symbol
type

ownership
lifetime

stateAtCursor

borrowers
moveSite

arena
scope
```

---

# 56. Vir Semantic State

Một semantic state thống nhất:

```text
SymbolState {
    symbolId

    reachable
    active

    initialized

    ownership

    borrowed
    borrowKind

    moved
    consumed

    arenaId

    visible
    exported
}
```

Editor chỉ việc render.

Không để VS Code extension tự suy luận semantic state.

---

# 57. Server Architecture

```text
vir-lsp
│
├── protocol/
│   ├── transport
│   ├── requests
│   ├── notifications
│   └── capabilities
│
├── workspace/
│   ├── source_db
│   ├── file_manager
│   ├── module_graph
│   └── dependency_graph
│
├── syntax/
│   ├── incremental_lexer
│   ├── parser
│   ├── recovery
│   └── syntax_tree
│
├── semantic/
│   ├── symbol_db
│   ├── scope_graph
│   ├── type_db
│   ├── reference_db
│   ├── call_graph
│   └── visibility
│
├── ownership/
│   ├── lifetime_db
│   ├── borrow_graph
│   ├── move_analysis
│   ├── arena_graph
│   └── escape_analysis
│
├── analysis/
│   ├── query_engine
│   ├── invalidation
│   ├── diagnostics
│   └── reachability
│
├── features/
│   ├── completion
│   ├── hover
│   ├── goto
│   ├── references
│   ├── rename
│   ├── semantic_tokens
│   ├── inlay_hints
│   ├── code_actions
│   ├── call_hierarchy
│   └── code_lens
│
└── extensions/
    ├── lifetime
    ├── borrow_graph
    ├── arena_graph
    └── value_flow
```

---

# 58. Tầng compiler dùng chung

Không nên:

```text
virc semantic engine

vir-lsp semantic engine khác
```

Mà:

```text
             vir-core
                │
      ┌─────────┼─────────┐
      ▼         ▼         ▼
    virc      vir-lsp    tools
```

`vir-core` chứa:

```text
lexer
parser
AST
HIR

name resolution
type system
borrow checker
arena analysis
control flow
diagnostics
```

Compiler tiếp tục:

```text
HIR
 ↓
MIR
 ↓
LIR
 ↓
RA
 ↓
codegen
```

LSP dừng chủ yếu tại:

```text
AST/HIR + semantic model
```

---

# 59. Performance Requirements

Interactive target:

```text
hover             < 30 ms ideal
go to definition  < 30 ms
completion        < 50 ms
signature help    < 50 ms

incremental syntax
                   < 20 ms typical

local diagnostics < 100 ms

deep diagnostics  asynchronous/debounced
```

Không cần hard guarantee nhưng phải lấy các con số này làm performance budget.

Phải đo:

```text
P50
P95
P99
```

Không chỉ average.

---

# 60. Memory Requirements

Không giữ mọi historical syntax tree.

Cache phải:

```text
version-aware
dependency-aware
bounded
evictable
```

Priority:

```text
open files
visible files
recent files
dependency interfaces
workspace index
```

---

# 61. Vir LSP Differentiator

Một LSP thông thường trả lời:

```text
What symbol is this?
What type is this?
Where is this declared?
```

Vir LSP nên trả lời thêm:

```text
Who owns this value?

Where is it allocated?

Which arena owns it?

When does its lifetime begin?

When does it end?

Who currently borrows it?

Is the borrow shared or mutable?

Where is the value moved?

Where is it consumed?

Can this value escape its arena?

Is this function reachable?

Which call activates it?

Is this include active?

Is this module actually used?

Does this symbol exist but remain unexported?

Where does this value flow?

Why exactly is this access invalid?
```

Đó mới nên là định nghĩa của `vir-lsp`.

---

# 62. Definition of Done

Vir LSP chỉ nên coi là baseline-complete khi:

```text
[ ] syntax diagnostics
[ ] declaration diagnostics
[ ] type diagnostics

[ ] include/import resolution
[ ] missing import detection
[ ] unexported symbol detection
[ ] unused imports

[ ] completion
[ ] hover
[ ] signature help

[ ] go to definition
[ ] go to declaration
[ ] go to type definition

[ ] find references
[ ] semantic rename

[ ] document symbols
[ ] workspace symbols

[ ] semantic tokens
[ ] inlay hints

[ ] call hierarchy
[ ] code actions

[ ] lifetime analysis
[ ] borrow diagnostics
[ ] move/use-after-move diagnostics
[ ] arena escape diagnostics

[ ] read/write reference classification
[ ] borrow/move reference classification

[ ] active/inactive functions
[ ] active/inactive modules/includes

[ ] lifetime visualization API
[ ] borrow graph API
[ ] arena graph API
[ ] value-flow API

[ ] incremental analysis
[ ] cancellation
[ ] broken-code recovery
[ ] version-safe diagnostics
```

## Kiến trúc cốt lõi

Cuối cùng có thể rút toàn hệ thống về công thức:

```text
Source
  ↓
Incremental Syntax
  ↓
Semantic Graph
  ├── Symbol Graph
  ├── Scope Graph
  ├── Type Graph
  ├── Module Graph
  ├── Call Graph
  ├── Reference Graph
  ├── Borrow Graph
  ├── Lifetime Graph
  └── Arena Graph
  ↓
Incremental Query Engine
  ↓
LSP Features
```

Trong đó:

```text
SymbolId
TypeId
ScopeId
ModuleId
ArenaId
BorrowId
```

phải là identity ổn định xuyên suốt toàn bộ analysis.

**Vir LSP không nên chỉ là “autocomplete cho Vir”. Nó nên là giao diện realtime của semantic engine và borrow checker của Vir.**