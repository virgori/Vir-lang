"""
ja.py – Japanese SubLib Adapter (日本語)
=========================================
Maps Japanese natural language phrases → lib TokenKind.
"""

from __future__ import annotations

from src.lib.keywords import TokenKind
from src.sublib.base import PhraseEntry, SubLibAdapter, SubLibRegistry


@SubLibRegistry.register
class JapaneseAdapter(SubLibAdapter):
    """日本語 → TokenKind アダプター"""

    @property
    def lang_code(self) -> str:
        return "ja"

    @property
    def lang_name(self) -> str:
        return "日本語"

    def _define_phrases(self) -> list[PhraseEntry]:
        P = PhraseEntry
        K = TokenKind
        return [
            # ── 定義 ──────────────────────────────────────
            P("関数",           K.FUNC_DEF,     "definition"),
            P("関数を定義",     K.FUNC_DEF,     "definition"),
            P("関数を作る",     K.FUNC_DEF,     "definition"),

            P("変数",           K.VAR_DECL,     "definition"),
            P("変数を宣言",     K.VAR_DECL,     "definition"),
            P("変数を定義",     K.VAR_DECL,     "definition"),
            P("代入",           K.VAR_DECL,     "definition"),

            P("定数",           K.CONST_DECL,   "definition"),
            P("定数を宣言",     K.CONST_DECL,   "definition"),

            P("クラス",         K.CLASS_DEF,    "definition"),
            P("クラスを定義",   K.CLASS_DEF,    "definition"),

            P("インポート",     K.IMPORT,       "definition"),
            P("読み込む",       K.IMPORT,       "definition"),

            P("エクスポート",   K.EXPORT,       "definition"),
            P("公開する",       K.EXPORT,       "definition"),

            # ── 制御フロー ────────────────────────────────
            P("もし",           K.IF,           "control_flow"),
            P("もしも",         K.IF,           "control_flow"),
            P("場合",           K.IF,           "control_flow"),
            P("条件",           K.IF,           "control_flow"),

            P("それ以外",       K.ELSE,         "control_flow"),
            P("でなければ",     K.ELSE,         "control_flow"),
            P("そうでなければ", K.ELSE,         "control_flow"),

            P("それ以外もし",   K.EIF,         "control_flow"),
            P("でなければもし", K.EIF,         "control_flow"),

            P("繰り返す",       K.LOOP,         "control_flow"),
            P("繰り返し",       K.LOOP,         "control_flow"),
            P("ループ",         K.LOOP,         "control_flow"),

            P("の間",           K.WHEN,        "control_flow"),
            P("間ずっと",       K.WHEN,        "control_flow"),
            P("している間",     K.WHEN,        "control_flow"),

            P("それぞれ",       K.FOR,          "control_flow"),
            P("各要素について", K.FOR,          "control_flow"),

            P("抜ける",         K.BREAK,        "control_flow"),
            P("ループを抜ける", K.BREAK,        "control_flow"),
            P("中断",           K.BREAK,        "control_flow"),

            P("次へ",           K.SKIP,        "control_flow"),
            P("スキップ",       K.SKIP,        "control_flow"),

            P("戻す",           K.OUT,         "control_flow"),
            P("返す",           K.OUT,         "control_flow"),
            P("結果は",         K.OUT,         "control_flow"),
            P("戻り値",         K.OUT,         "control_flow"),

            P("照合",           K.CASE,        "control_flow"),
            P("パターン",       K.CASE,        "control_flow"),
            P("ケース",         K.CASE,         "control_flow"),

            # ── 算術 ──────────────────────────────────────
            P("足す",           K.OP_ADD,       "arithmetic"),
            P("足し算",         K.OP_ADD,       "arithmetic"),
            P("加算",           K.OP_ADD,       "arithmetic"),
            P("プラス",         K.OP_ADD,       "arithmetic"),

            P("引く",           K.OP_SUB,       "arithmetic"),
            P("引き算",         K.OP_SUB,       "arithmetic"),
            P("減算",           K.OP_SUB,       "arithmetic"),
            P("マイナス",       K.OP_SUB,       "arithmetic"),

            P("掛ける",         K.OP_MUL,       "arithmetic"),
            P("掛け算",         K.OP_MUL,       "arithmetic"),
            P("乗算",           K.OP_MUL,       "arithmetic"),

            P("割る",           K.OP_DIV,       "arithmetic"),
            P("割り算",         K.OP_DIV,       "arithmetic"),
            P("除算",           K.OP_DIV,       "arithmetic"),

            P("余り",           K.OP_MOD,       "arithmetic"),
            P("剰余",           K.OP_MOD,       "arithmetic"),

            P("べき乗",         K.OP_POW,       "arithmetic"),
            P("累乗",           K.OP_POW,       "arithmetic"),

            # ── 比較 ──────────────────────────────────────
            P("等しい",         K.CMP_EQ,       "comparison"),
            P("同じ",           K.CMP_EQ,       "comparison"),
            P("イコール",       K.CMP_EQ,       "comparison"),

            P("等しくない",     K.CMP_NE,       "comparison"),
            P("違う",           K.CMP_NE,       "comparison"),

            P("より大きい",     K.CMP_GT,       "comparison"),
            P("超える",         K.CMP_GT,       "comparison"),

            P("より小さい",     K.CMP_LT,       "comparison"),
            P("未満",           K.CMP_LT,       "comparison"),

            P("以上",           K.CMP_GE,       "comparison"),
            P("以下",           K.CMP_LE,       "comparison"),

            # ── 論理 ──────────────────────────────────────
            P("かつ",           K.LOGIC_AND,    "logical"),
            P("そして",         K.LOGIC_AND,    "logical"),

            P("または",         K.LOGIC_OR,     "logical"),
            P("あるいは",       K.LOGIC_OR,     "logical"),

            P("ではない",       K.LOGIC_NOT,    "logical"),
            P("否定",           K.LOGIC_NOT,    "logical"),

            # ── 入出力 ────────────────────────────────────
            P("表示する",       K.PRINT,        "io"),
            P("出力する",       K.PRINT,        "io"),
            P("印刷する",       K.PRINT,        "io"),
            P("書き出す",       K.PRINT,        "io"),

            P("入力する",       K.INPUT,        "io"),
            P("読み取る",       K.INPUT,        "io"),
            P("キーボードから", K.INPUT,        "io"),

            # ── 型 ────────────────────────────────────────
            P("整数",           K.TYPE_INT,     "type"),
            P("浮動小数点",     K.TYPE_FLOAT,   "type"),
            P("文字列",         K.TYPE_STRING,  "type"),
            P("真偽値",         K.TYPE_BOOL,    "type"),
            P("配列",           K.TYPE_ARRAY,   "type"),
            P("辞書",           K.TYPE_MAP,     "type"),

            # ── 真偽 / null ───────────────────────────────
            P("真",             K.TRUE,         "literal"),
            P("偽",             K.FALSE,        "literal"),
            P("なし",           K.NONE,         "literal"),
            P("空",             K.NONE,         "literal"),

            # ── システム ──────────────────────────────────
            P("CPU確認",        K.CHECK_CPU,    "system"),
            P("CPUが空いている", K.CHECK_CPU,   "system"),

            P("パッチ",         K.PATCH,        "system"),
            P("最適化",         K.PATCH,        "system"),

            P("レジスタ",       K.TARGET_REGISTER, "system"),
            P("レジスタで",     K.TARGET_REGISTER, "system"),

            P("実行する",       K.EXECUTE,      "system"),
            P("走らせる",       K.EXECUTE,      "system"),
            P("開始",           K.EXECUTE,      "system"),

            P("スリープ",       K.SLEEP,        "system"),
            P("待つ",           K.SLEEP,        "system"),
        ]

    def _define_stop_words(self) -> list[str]:
        return [
            "の", "は", "が", "を", "に", "で", "と", "も",
            "から", "まで", "よ", "ね", "な", "か", "わ",
            "です", "ます", "だ", "ある", "いる", "する",
            "この", "その", "あの", "どの", "これ", "それ",
        ]
