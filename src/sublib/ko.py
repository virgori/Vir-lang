"""
ko.py – Korean SubLib Adapter (한국어)
========================================
Maps Korean natural language phrases → lib TokenKind.
"""

from __future__ import annotations

from src.lib.keywords import TokenKind
from src.sublib.base import PhraseEntry, SubLibAdapter, SubLibRegistry


@SubLibRegistry.register
class KoreanAdapter(SubLibAdapter):
    """한국어 → TokenKind 어댑터"""

    @property
    def lang_code(self) -> str:
        return "ko"

    @property
    def lang_name(self) -> str:
        return "한국어"

    def _define_phrases(self) -> list[PhraseEntry]:
        P = PhraseEntry
        K = TokenKind
        return [
            # ── 정의 ──────────────────────────────────────
            P("함수",         K.FUNC_DEF,     "definition"),
            P("함수 정의",    K.FUNC_DEF,     "definition"),
            P("함수 만들기",  K.FUNC_DEF,     "definition"),

            P("변수",         K.VAR_DECL,     "definition"),
            P("변수 선언",    K.VAR_DECL,     "definition"),
            P("할당",         K.VAR_DECL,     "definition"),

            P("상수",         K.CONST_DECL,   "definition"),
            P("상수 선언",    K.CONST_DECL,   "definition"),

            P("클래스",       K.CLASS_DEF,    "definition"),
            P("클래스 정의",  K.CLASS_DEF,    "definition"),

            P("가져오기",     K.IMPORT,       "definition"),
            P("임포트",       K.IMPORT,       "definition"),

            P("내보내기",     K.EXPORT,       "definition"),
            P("공개",         K.EXPORT,       "definition"),

            # ── 제어 흐름 ─────────────────────────────────
            P("만약",         K.IF,           "control_flow"),
            P("만일",         K.IF,           "control_flow"),
            P("조건",         K.IF,           "control_flow"),

            P("아니면",       K.ELSE,         "control_flow"),
            P("그렇지 않으면", K.ELSE,        "control_flow"),

            P("아니면 만약",  K.EIF,         "control_flow"),

            P("반복",         K.LOOP,         "control_flow"),
            P("반복하기",     K.LOOP,         "control_flow"),

            P("동안",         K.WHEN,        "control_flow"),
            P("하는 동안",    K.WHEN,        "control_flow"),

            P("각각",         K.FOR,          "control_flow"),
            P("하나씩",       K.FOR,          "control_flow"),

            P("중단",         K.BREAK,        "control_flow"),
            P("루프 탈출",    K.BREAK,        "control_flow"),

            P("계속",         K.SKIP,        "control_flow"),
            P("건너뛰기",     K.SKIP,        "control_flow"),

            P("반환",         K.OUT,         "control_flow"),
            P("결과는",       K.OUT,         "control_flow"),
            P("돌려주기",     K.OUT,         "control_flow"),

            # ── 산술 ──────────────────────────────────────
            P("더하기",       K.OP_ADD,       "arithmetic"),
            P("덧셈",         K.OP_ADD,       "arithmetic"),
            P("합",           K.OP_ADD,       "arithmetic"),

            P("빼기",         K.OP_SUB,       "arithmetic"),
            P("뺄셈",         K.OP_SUB,       "arithmetic"),

            P("곱하기",       K.OP_MUL,       "arithmetic"),
            P("곱셈",         K.OP_MUL,       "arithmetic"),

            P("나누기",       K.OP_DIV,       "arithmetic"),
            P("나눗셈",       K.OP_DIV,       "arithmetic"),

            P("나머지",       K.OP_MOD,       "arithmetic"),
            P("거듭제곱",     K.OP_POW,       "arithmetic"),

            # ── 비교 ──────────────────────────────────────
            P("같다",         K.CMP_EQ,       "comparison"),
            P("같으면",       K.CMP_EQ,       "comparison"),

            P("다르다",       K.CMP_NE,       "comparison"),
            P("같지 않다",    K.CMP_NE,       "comparison"),

            P("크다",         K.CMP_GT,       "comparison"),
            P("보다 크다",    K.CMP_GT,       "comparison"),

            P("작다",         K.CMP_LT,       "comparison"),
            P("보다 작다",    K.CMP_LT,       "comparison"),

            P("이상",         K.CMP_GE,       "comparison"),
            P("이하",         K.CMP_LE,       "comparison"),

            # ── 논리 ──────────────────────────────────────
            P("그리고",       K.LOGIC_AND,    "logical"),
            P("또는",         K.LOGIC_OR,     "logical"),
            P("아닌",         K.LOGIC_NOT,    "logical"),

            # ── 입출력 ────────────────────────────────────
            P("출력",         K.PRINT,        "io"),
            P("표시",         K.PRINT,        "io"),
            P("인쇄",         K.PRINT,        "io"),

            P("입력",         K.INPUT,        "io"),
            P("읽기",         K.INPUT,        "io"),

            # ── 타입 ──────────────────────────────────────
            P("정수",         K.TYPE_INT,     "type"),
            P("실수",         K.TYPE_FLOAT,   "type"),
            P("문자열",       K.TYPE_STRING,  "type"),
            P("참거짓",       K.TYPE_BOOL,    "type"),
            P("배열",         K.TYPE_ARRAY,   "type"),
            P("사전",         K.TYPE_MAP,     "type"),

            # ── 참/거짓 ───────────────────────────────────
            P("참",           K.TRUE,         "literal"),
            P("거짓",         K.FALSE,        "literal"),
            P("없음",         K.NONE,         "literal"),

            # ── 시스템 ────────────────────────────────────
            P("CPU 확인",     K.CHECK_CPU,    "system"),
            P("CPU 한가함",   K.CHECK_CPU,    "system"),

            P("패치",         K.PATCH,        "system"),
            P("최적화",       K.PATCH,        "system"),

            P("레지스터",     K.TARGET_REGISTER, "system"),

            P("실행",         K.EXECUTE,      "system"),
            P("시작",         K.EXECUTE,      "system"),

            P("대기",         K.SLEEP,        "system"),
        ]

    def _define_stop_words(self) -> list[str]:
        return [
            "은", "는", "이", "가", "을", "를", "에", "에서",
            "의", "로", "으로", "와", "과", "도", "좀", "잠깐",
            "하다", "하는", "해서", "하면", "할", "합니다",
            "이것", "그것", "저것", "여기", "거기", "저기",
        ]
