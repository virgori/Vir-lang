"""
vi.py – Vietnamese SubLib Adapter (Tiếng Việt)
================================================
Maps Vietnamese natural language phrases → lib TokenKind.

Design: Multiple phrasings per concept – the user can write naturally
and the tokenizer finds the longest matching N-gram.
"""

from __future__ import annotations

from src.lib.keywords import TokenKind
from src.sublib.base import PhraseEntry, SubLibAdapter, SubLibRegistry


@SubLibRegistry.register
class VietnameseAdapter(SubLibAdapter):
    """Bộ ánh xạ Tiếng Việt → TokenKind chuẩn."""

    @property
    def lang_code(self) -> str:
        return "vi"

    @property
    def lang_name(self) -> str:
        return "Tiếng Việt"

    def _define_phrases(self) -> list[PhraseEntry]:
        P = PhraseEntry
        K = TokenKind
        return [
            # ── Định nghĩa ────────────────────────────────
            P("ta có hàm",       K.FUNC_DEF,    "definition"),
            P("tạo hàm",         K.FUNC_DEF,    "definition"),
            P("định nghĩa",      K.FUNC_DEF,    "definition"),
            P("khai báo hàm",    K.FUNC_DEF,    "definition"),
            P("viết hàm",        K.FUNC_DEF,    "definition"),
            P("hàm",             K.FUNC_DEF,    "definition"),

            P("cho biến",        K.VAR_DECL,    "definition"),
            P("đặt biến",        K.VAR_DECL,    "definition"),
            P("gán",             K.VAR_DECL,    "definition"),
            P("ta có biến",      K.VAR_DECL,    "definition"),
            P("khai báo biến",   K.VAR_DECL,    "definition"),
            P("biến",            K.VAR_DECL,    "definition"),

            P("hằng số",         K.CONST_DECL,  "definition"),
            P("khai báo hằng",   K.CONST_DECL,  "definition"),

            P("lớp",             K.CLASS_DEF,   "definition"),
            P("tạo lớp",         K.CLASS_DEF,   "definition"),

            P("nhập khẩu",       K.IMPORT,      "definition"),
            P("dùng",            K.IMPORT,      "definition"),
            P("nạp",             K.IMPORT,      "definition"),

            P("xuất khẩu",       K.EXPORT,      "definition"),
            P("công khai",       K.EXPORT,      "definition"),

            # ── Điều khiển luồng ───────────────────────────
            P("nếu",             K.IF,          "control_flow"),
            P("nếu mà",          K.IF,          "control_flow"),
            P("giả sử",          K.IF,          "control_flow"),
            P("trong trường hợp", K.IF,         "control_flow"),
            P("khi mà",          K.IF,          "control_flow"),
            P("lúc mà",          K.IF,          "control_flow"),

            P("ngược lại",       K.ELSE,        "control_flow"),
            P("nếu không",       K.ELSE,        "control_flow"),
            P("còn không thì",   K.ELSE,        "control_flow"),
            P("không thì",       K.ELSE,        "control_flow"),

            P("còn nếu",         K.EIF,         "control_flow"),
            P("nếu không mà",    K.EIF,         "control_flow"),

            P("lặp lại",         K.LOOP,        "control_flow"),
            P("vòng lặp",        K.LOOP,        "control_flow"),
            P("lặp",             K.LOOP,        "control_flow"),
            P("chạy vòng",       K.LOOP,        "control_flow"),

            P("trong khi",       K.WHEN,        "control_flow"),
            P("khi mà còn",      K.WHEN,        "control_flow"),
            P("lặp khi",         K.WHEN,        "control_flow"),

            P("với mỗi",         K.FOR,         "control_flow"),
            P("duyệt",           K.FOR,         "control_flow"),
            P("lần lượt",        K.FOR,         "control_flow"),

            P("thoát vòng",      K.BREAK,       "control_flow"),
            P("dừng lặp",        K.BREAK,       "control_flow"),

            P("bỏ qua",          K.SKIP,        "control_flow"),
            P("tiếp tục",        K.SKIP,        "control_flow"),

            P("trả về",          K.OUT,         "control_flow"),
            P("kết quả là",      K.OUT,         "control_flow"),
            P("trả lại",         K.OUT,         "control_flow"),
            P("xuất ra",         K.OUT,         "control_flow"),

            P("so khớp",         K.CASE,        "control_flow"),
            P("trường hợp",      K.CASE,        "control_flow"),

            P("thực thể",        K.ENTITY_DEF,  "definition"),
            P("đối tượng",       K.ENTITY_DEF,  "definition"),

            P("phương thức",     K.METHOD_DEF,  "definition"),
            P("hành vi",         K.METHOD_DEF,  "definition"),

            P("có sẵn",          K.HAS,         "definition"),
            P("khai báo trước",  K.HAS,         "definition"),

            P("chia sẻ",         K.SHARE,       "definition"),
            P("dùng chung",      K.SHARE,       "definition"),

            P("lấy",             K.GET,         "definition"),
            P("nhận",            K.GET,         "definition"),

            P("từ",              K.FROM,        "definition"),

            P("kết thúc",        K.END,         "control_flow"),
            P("xong",            K.END,         "control_flow"),
            P("hết",             K.END,         "control_flow"),

            P("tham số",         K.IN,          "definition"),
            P("đầu vào",         K.IN,          "definition"),

            P("bất đồng bộ",     K.ASYNC,       "concurrency"),
            P("nhiệm vụ",        K.TASK,        "concurrency"),
            P("chờ đợi",         K.WAIT,        "concurrency"),

            P("thử",             K.TRY,         "error_handling"),
            P("lỗi",             K.ERROR,       "error_handling"),

            P("ánh xạ",          K.MAP,         "data_structure"),
            P("bản đồ",          K.MAP,         "data_structure"),

            P("phần trăm",       K.OP_PERCENT,  "arithmetic"),
            P("phép dư",         K.OP_MOD,      "arithmetic"),

            P("bao gồm",         K.INCLUDE,    "module"),
            P("nạp vào",         K.INCLUDE,    "module"),

            # ── Phép toán ──────────────────────────────────
            P("tính tổng",       K.OP_ADD,      "arithmetic"),
            P("cộng",            K.OP_ADD,      "arithmetic"),
            P("tính cộng",       K.OP_ADD,      "arithmetic"),
            P("cộng lại",        K.OP_ADD,      "arithmetic"),

            P("tính hiệu",       K.OP_SUB,     "arithmetic"),
            P("trừ",             K.OP_SUB,      "arithmetic"),
            P("tính trừ",        K.OP_SUB,      "arithmetic"),
            P("trừ đi",          K.OP_SUB,      "arithmetic"),

            P("tính tích",       K.OP_MUL,      "arithmetic"),
            P("nhân",            K.OP_MUL,      "arithmetic"),
            P("tính nhân",       K.OP_MUL,      "arithmetic"),
            P("nhân lại",        K.OP_MUL,      "arithmetic"),

            P("tính thương",     K.OP_DIV,      "arithmetic"),
            P("chia",            K.OP_DIV,      "arithmetic"),
            P("tính chia",       K.OP_DIV,      "arithmetic"),
            P("chia cho",        K.OP_DIV,      "arithmetic"),

            P("chia dư",         K.OP_MOD,      "arithmetic"),
            P("phần dư",         K.OP_MOD,      "arithmetic"),

            P("lũy thừa",        K.OP_POW,     "arithmetic"),
            P("mũ",              K.OP_POW,      "arithmetic"),

            # ── So sánh ────────────────────────────────────
            P("bằng",            K.CMP_EQ,      "comparison"),
            P("bằng nhau",       K.CMP_EQ,      "comparison"),
            P("giống nhau",      K.CMP_EQ,      "comparison"),

            P("khác",            K.CMP_NE,      "comparison"),
            P("không bằng",      K.CMP_NE,      "comparison"),
            P("khác nhau",       K.CMP_NE,      "comparison"),

            P("lớn hơn",         K.CMP_GT,      "comparison"),
            P("nhiều hơn",       K.CMP_GT,      "comparison"),
            P("cao hơn",         K.CMP_GT,      "comparison"),

            P("nhỏ hơn",         K.CMP_LT,      "comparison"),
            P("ít hơn",          K.CMP_LT,      "comparison"),
            P("thấp hơn",        K.CMP_LT,      "comparison"),

            P("lớn hơn hoặc bằng",  K.CMP_GE,  "comparison"),
            P("không nhỏ hơn",       K.CMP_GE,  "comparison"),

            P("nhỏ hơn hoặc bằng",  K.CMP_LE,  "comparison"),
            P("không lớn hơn",       K.CMP_LE,  "comparison"),

            # ── Logic ──────────────────────────────────────
            P("và",              K.LOGIC_AND,   "logical"),
            P("đồng thời",       K.LOGIC_AND,  "logical"),

            P("hoặc",            K.LOGIC_OR,    "logical"),
            P("hay là",          K.LOGIC_OR,    "logical"),

            P("phủ định",        K.LOGIC_NOT,   "logical"),
            P("không phải",      K.LOGIC_NOT,   "logical"),

            # ── I/O ────────────────────────────────────────
            P("in ra",           K.PRINT,       "io"),
            P("hiển thị",        K.PRINT,       "io"),
            P("xuất",            K.PRINT,       "io"),
            P("cho xem",         K.PRINT,       "io"),
            P("viết ra",         K.PRINT,       "io"),

            P("nhập vào",        K.INPUT,       "io"),
            P("đọc vào",         K.INPUT,       "io"),
            P("lấy từ bàn phím", K.INPUT,      "io"),
            P("hỏi người dùng",  K.INPUT,      "io"),

            # ── Kiểu dữ liệu ──────────────────────────────
            P("số nguyên",       K.TYPE_INT,    "type"),
            P("số thực",         K.TYPE_FLOAT,  "type"),
            P("chuỗi",           K.TYPE_STRING, "type"),
            P("đúng sai",        K.TYPE_BOOL,   "type"),
            P("mảng",            K.TYPE_ARRAY,  "type"),
            P("từ điển",         K.TYPE_MAP,    "type"),

            # ── Boolean / null ─────────────────────────────
            P("đúng",            K.TRUE,        "literal"),
            P("sai",             K.FALSE,       "literal"),
            P("không có gì",     K.NONE,        "literal"),
            P("rỗng",            K.NONE,        "literal"),

            # ── Hệ thống ──────────────────────────────────
            P("máy rảnh",        K.CHECK_CPU,   "system"),
            P("cpu rảnh",        K.CHECK_CPU,   "system"),
            P("kiểm tra cpu",    K.CHECK_CPU,   "system"),
            P("kiểm tra máy",    K.CHECK_CPU,   "system"),

            P("vá mã",           K.PATCH,       "system"),
            P("tối ưu",          K.PATCH,       "system"),
            P("patch",           K.PATCH,       "system"),
            P("vá lỗi",          K.PATCH,       "system"),

            P("thanh ghi",       K.TARGET_REGISTER, "system"),
            P("dùng thanh ghi",  K.TARGET_REGISTER, "system"),
            P("bằng thanh ghi",  K.TARGET_REGISTER, "system"),

            P("chạy",            K.EXECUTE,     "system"),
            P("thực thi",        K.EXECUTE,     "system"),
            P("thực hiện",       K.EXECUTE,     "system"),
            P("bắt đầu",         K.EXECUTE,    "system"),

            P("ngủ",             K.SLEEP,       "system"),
            P("chờ",             K.SLEEP,       "system"),
            P("đợi",             K.SLEEP,       "system"),
        ]

    def _define_stop_words(self) -> list[str]:
        return [
            "thì", "là", "nhé", "giúp", "ơi", "đi", "nào", "với", "được",
            "cái", "này", "kia", "đó", "ấy", "mà", "rồi", "vậy", "thôi",
            "hãy", "xin", "cho", "tôi", "bạn", "ta", "của", "và", "hay",
            "hoặc", "cùng", "để", "ra", "vào", "lên", "xuống",
        ]
