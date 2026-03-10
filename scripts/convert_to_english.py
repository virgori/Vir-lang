#!/usr/bin/env python3
"""
convert_to_english.py — Vir Pure Build: Vietnamese → English v1.2
=================================================================
Converts all .vri files from Vietnamese keywords to standard English syntax.

Keyword mapping (Vietnamese → English v1.2):

  nhập        → import
  dùng hết    → use all
  dùng        → use
  hàm         → func
  biến        → var
  hằng        → const
  kiểu        → type
  liệt_kê    → enum
  bản_ghi     → entity
  nếu         → if
  ngược_lại   → else
  thì         → end  (block opener → block closer in v1.2)
  hết         → end
  trong_khi   → when ... loop
  trả_về      → out
  trả về      → out
  đúng        → true
  sai         → false
  không_gì    → none
  hoặc        → or
  và          → and
  dưới_dạng   → as
  như          → as  (casting keyword)
"""

import os
import re
import sys
from pathlib import Path


def convert_file(filepath: str) -> tuple[int, str]:
    """Convert a single .vri file. Returns (changes_count, new_content)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    changes = 0

    # ─── Phase 1: Multi-word replacements (order matters) ───

    # "dùng hết" → "use all" (must come before "dùng")
    content, n = re.subn(r'\bdùng hết\b', 'use all', content)
    changes += n

    # "trả_về" → "out" and "trả về" → "out"
    content, n = re.subn(r'\btrả_về\b', 'out', content)
    changes += n
    content, n = re.subn(r'\btrả về\b', 'out', content)
    changes += n

    # "trong_khi" → "while" (we'll use "while" for now, simpler than when...loop)
    content, n = re.subn(r'\btrong_khi\b', 'while', content)
    changes += n

    # "ngược_lại" → "else"
    content, n = re.subn(r'\bngược_lại\b', 'else', content)
    changes += n

    # "bản_ghi" → "entity"
    content, n = re.subn(r'\bbản_ghi\b', 'entity', content)
    changes += n

    # "liệt_kê" → "enum"
    content, n = re.subn(r'\bliệt_kê\b', 'enum', content)
    changes += n

    # "dưới_dạng" → "as"
    content, n = re.subn(r'\bdưới_dạng\b', 'as', content)
    changes += n

    # "không_gì" → "none"
    content, n = re.subn(r'\bkhông_gì\b', 'none', content)
    changes += n

    # ─── Phase 2: Single-word replacements ───

    # "nhập" → "import" (at start of import statement)
    content, n = re.subn(r'\bnhập\b', 'import', content)
    changes += n

    # "dùng" → "use" (after "dùng hết" already replaced)
    content, n = re.subn(r'\bdùng\b', 'use', content)
    changes += n

    # "hàm" → "func"
    content, n = re.subn(r'\bhàm\b', 'func', content)
    changes += n

    # "biến" → "var"
    content, n = re.subn(r'\bbiến\b', 'var', content)
    changes += n

    # "hằng" → "const"
    content, n = re.subn(r'\bhằng\b', 'const', content)
    changes += n

    # "kiểu" → "type"
    content, n = re.subn(r'\bkiểu\b', 'type', content)
    changes += n

    # "nếu" → "if"
    content, n = re.subn(r'\bnếu\b', 'if', content)
    changes += n

    # "thì" → "end" (block opener in Vietnamese → block end marker)
    # In Vietnamese Vir, "thì" opens a block. In English v1.2, blocks are
    # closed by "end" and opened implicitly after the condition/declaration line.
    # We need careful handling: "thì" at end of line → remove (implicit block open)
    # But "thì" as standalone → "end"
    # Actually looking at the code: "nếu x thì" / "hàm foo() thì" — "thì" is the block opener
    # The English equivalent just has no "then" — the block starts after the line
    # So we remove "thì" when at end of line (after condition), but keep "hết" → "end"
    content, n = re.subn(r'\s+thì\s*$', '', content, flags=re.MULTILINE)
    changes += n
    # Also handle "thì" followed by newline mid-line
    content, n = re.subn(r'\s+thì\s*\n', '\n', content)
    changes += n

    # "hết" → "end"
    content, n = re.subn(r'\bhết\b', 'end', content)
    changes += n

    # "đúng" → "true"
    content, n = re.subn(r'\bđúng\b', 'true', content)
    changes += n

    # "sai" → "false"
    content, n = re.subn(r'\bsai\b', 'false', content)
    changes += n

    # "hoặc" → "or"
    content, n = re.subn(r'\bhoặc\b', 'or', content)
    changes += n

    # "và" → "and" (word boundary)
    content, n = re.subn(r'\bvà\b', 'and', content)
    changes += n

    # "như" as casting → "as" (only when used for type casting: "x như i32")
    content, n = re.subn(r'\bnhư\b', 'as', content)
    changes += n

    # ─── Phase 3: Vietnamese comments → English ───
    # Comprehensive Vietnamese → English comment/doc translation
    vi_comment_map = {
        # Type system comments
        r'# Kiểu số nguyên có dấu \(signed integers\)': '# Signed integer types',
        r'# Kiểu số nguyên không dấu \(unsigned integers\)': '# Unsigned integer types',
        r'# Kiểu số thực \(floating point - IEEE 754\)': '# Floating point types (IEEE 754)',
        r'# Kiểu cơ bản khác': '# Other fundamental types',
        r'# Kiểu kích thước \(từ C23 <stddef.h>\)': '# Size types (from C23 <stddef.h>)',
        r'# Giới hạn kiểu \(từ C23 <limits.h> \+ <float.h>\)': '# Type limits (from C23 <limits.h> + <float.h>)',
        r'# Hàm chuyển đổi kiểu': '# Type conversion functions',
    }
    for vi_pat, en_repl in vi_comment_map.items():
        content, n = re.subn(vi_pat, en_repl, content)
        changes += n

    # ─── Phase 4: Translate remaining Vietnamese fragments ───
    vi_words = {
        # Doc header patterns
        'Học từ': 'Inspired by',
        'Đây là nền tảng': 'This is the foundation',
        'Kiểu nguyên thủy & giới hạn': 'Primitive types & limits',
        # Common words in comments
        'mặc định': 'default',
        'mọi module khác đều phụ thuộc': 'all other modules depend on',
        'Compiler tự dùng': 'Compiler uses internally',
        'Compiler tự use': 'Compiler uses internally',
        'cho dữ liệu nhị phân': 'for binary data',
        'con trỏ thô': 'raw pointer',
        'kiểu rỗng': 'void type',
        'type rỗng': 'void type',
        'không trả giá trị': 'returns nothing',
        'bên trong': 'internally',
        'kích thước bằng pointer': 'pointer-sized',
        'trên 64-bit': 'on 64-bit',
        'cho registers': 'for registers',
        'cho byte buffer': 'for byte buffer',
        'cho flags': 'for flags',
        'cho "số"': 'for integers',
        'cho "thực"': 'for floats',
        'alias cho': 'alias for',
        'Truncate to': 'Truncate to',
        'panic nếu overflow': 'panic on overflow',
        # Phase/section headers
        'Pha ': 'Phase ',
        'Bước ': 'Step ',
        # Common fragments
        'dùng cho': 'used for',
        'nếu không': 'otherwise',
        'nếu có': 'if exists',
        'theo mặc định': 'by default',
        'Ví dụ': 'Example',
        'Ghi chú': 'Note',
        'Lưu ý': 'Warning',
        'Tham số': 'Parameters',
        'Trả về': 'Returns',
        'Giá trị trả về': 'Return value',
        'Xem thêm': 'See also',
        'Lỗi': 'Error',
        'Cảnh báo': 'Warning',
        'Yêu cầu': 'Requires',
        'Ngoại lệ': 'Exception',
        'Kết quả': 'Result',
        'Mô tả': 'Description',
        'Cú pháp': 'Syntax',
        'Đầu vào': 'Input',
        'Đầu ra': 'Output',
        'chưa được hỗ trợ': 'not yet supported',
        'không hợp lệ': 'invalid',
        'đã tồn tại': 'already exists',
        'không tìm thấy': 'not found',
        'rỗng': 'empty',
        'đầy': 'full',
        'tràn': 'overflow',
        'thiếu': 'missing',
        'thất bại': 'failed',
        'thành công': 'success',
        'đang chạy': 'running',
        'đã dừng': 'stopped',
        'chờ đợi': 'waiting',
        'kết nối': 'connection',
        'mở tệp': 'open file',
        'đóng tệp': 'close file',
        'đọc tệp': 'read file',
        'ghi tệp': 'write file',
        'thư mục': 'directory',
        'tệp tin': 'file',
        'luồng': 'thread',
        'khóa': 'lock',
        'mở khóa': 'unlock',
        'bộ nhớ': 'memory',
        'cấp phát': 'allocate',
        'giải phóng': 'deallocate',
        'bộ đệm': 'buffer',
        'con trỏ': 'pointer',
        'mảng': 'array',
        'chuỗi': 'string',
        'ký tự': 'character',
        'số nguyên': 'integer',
        'số thực': 'floating point',
        'phép toán': 'operation',
        'kết quả': 'result',
        'tùy chọn': 'option',
        'giá trị': 'value',
        'chỉ số': 'index',
        'độ dài': 'length',
        'kích thước': 'size',
        'dung lượng': 'capacity',
        'phần tử': 'element',
        'danh sách': 'list',
        'từ điển': 'dictionary',
        'tập hợp': 'set',
        'hàng đợi': 'queue',
        'ngăn xếp': 'stack',
        'nút': 'node',
        'cạnh': 'edge',
        'đồ thị': 'graph',
        'cây': 'tree',
        'gốc': 'root',
        'lá': 'leaf',
    }
    for vi, en in vi_words.items():
        content, n = re.subn(re.escape(vi), en, content)
        changes += n

    # ─── Phase 5: Fix arrow syntax ───
    # "→" → "->" (Unicode arrow to ASCII)
    content, n = re.subn(r'→', '->', content)
    changes += n

    if content != original:
        return changes, content
    return 0, content


def convert_directory(root_dir: str, dry_run: bool = False) -> dict:
    """Convert all .vri files in a directory tree."""
    stats = {'files': 0, 'changes': 0, 'skipped': 0, 'errors': []}

    for dirpath, _, filenames in os.walk(root_dir):
        for fname in sorted(filenames):
            if not fname.endswith('.vri'):
                continue

            filepath = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(filepath, root_dir)

            try:
                count, new_content = convert_file(filepath)

                if count > 0:
                    stats['files'] += 1
                    stats['changes'] += count

                    if not dry_run:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"  ✓ {rel_path} ({count} changes)")
                    else:
                        print(f"  [dry-run] {rel_path} ({count} changes)")
                else:
                    stats['skipped'] += 1

            except Exception as e:
                stats['errors'].append((rel_path, str(e)))
                print(f"  ✗ {rel_path}: {e}")

    return stats


def main():
    dry_run = '--dry-run' in sys.argv

    vir_root = Path(__file__).parent
    stdlib_dir = vir_root / 'stdlib'

    if not stdlib_dir.exists():
        print(f"Error: stdlib directory not found at {stdlib_dir}")
        sys.exit(1)

    print("=" * 60)
    print("Vir Pure Build — Vietnamese → English v1.2 Conversion")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN — no files will be modified]\n")
    else:
        print("\n[LIVE — files will be modified in place]\n")

    # Also convert any .vri files outside stdlib (e.g., examples, bootstrap)
    # But focus on stdlib first
    print("Converting stdlib/...")
    stats = convert_directory(str(stdlib_dir), dry_run)

    print(f"\n{'=' * 60}")
    print(f"Files converted: {stats['files']}")
    print(f"Total changes:   {stats['changes']}")
    print(f"Files skipped:   {stats['skipped']} (already English)")
    if stats['errors']:
        print(f"Errors:          {len(stats['errors'])}")
        for path, err in stats['errors']:
            print(f"  - {path}: {err}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
