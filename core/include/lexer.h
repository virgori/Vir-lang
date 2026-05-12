/*
 * lexer.h – Vir Source Lexer (Tokenizer)
 * =======================================
 * Converts UTF-8 source text into a token stream.
 * Supports Vietnamese and English keywords.
 *
 * Block delimiters: thì/then (begin), hết/end (close)
 */

#ifndef VIR_LEXER_H
#define VIR_LEXER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * Token Types
 * ═══════════════════════════════════════════════════════ */

typedef enum {
  TOK_EOF = 0,
  TOK_ERROR,

  /* ── Literals ──────────────────────────────────────── */
  TOK_INT,    /* 42, 0xFF                     */
  TOK_FLOAT,  /* 3.14                         */
  TOK_STRING, /* "hello" or 'hello'           */
  TOK_IDENT,  /* variable / function names    */

  /* ── Definitions ───────────────────────────────────── */
  TOK_FUNC,  /* hàm, func                    */
  TOK_VAR,   /* biến, var                    */
  TOK_CONST, /* hằng, const                  */

  /* ── Control flow ──────────────────────────────────── */
  TOK_IF,       /* nếu, if                      */
  TOK_ELSE,     /* ngược lại, else              */
  TOK_ELIF,     /* còn nếu, elif (legacy)       */
  TOK_EIF,      /* eif (v1.2 else-if)           */
  TOK_LOOP,     /* lặp, loop                    */
  TOK_WHILE,    /* trong khi, while (legacy)    */
  TOK_WHEN,     /* when (v1.2 conditional loop) */
  TOK_FOR,      /* với mỗi, for (legacy)        */
  TOK_BREAK,    /* thoát, break                 */
  TOK_CONTINUE, /* tiếp tục, continue (legacy)  */
  TOK_SKIP,     /* skip (v1.2 continue)         */
  TOK_RETURN,   /* trả về, return (legacy)      */
  TOK_OUT,      /* out (v1.2 return)            */
  TOK_CASE,     /* case (v1.2)                  */
  TOK_DEL,      /* del (§20 dict key removal)   */

  /* ── Block delimiters ──────────────────────────────── */
  TOK_THEN, /* thì, then (legacy)           */
  TOK_END,  /* hết, end                     */

  /* ── I/O ───────────────────────────────────────────── */
  TOK_PRINT, /* in ra, print                 */
  TOK_INPUT, /* nhập vào, input              */

  /* ── Type definitions ──────────────────────────────── */
  TOK_RECORD, /* bản_ghi, record (legacy)     */
  TOK_ENUM,   /* liệt_kê, enum                */
  TOK_ENTITY, /* entity (v1.2 struct)         */
  TOK_METHOD, /* method (v1.2)                */
  TOK_CLASS,  /* class (v1.2)                 */
  TOK_THIS,   /* this (v1.2 method self ref)  */

  /* ── Forward decl / sharing ────────────────────────── */
  TOK_HAS,   /* has (v1.2 forward decl)      */
  TOK_SHARE, /* share (v1.2 state sharing)   */
  TOK_GET,   /* get (v1.2 import shared)     */

  /* ── Async / concurrency ───────────────────────────── */
  TOK_ASYNC, /* async (v1.2)                 */
  TOK_TASK,  /* task (v1.2)                  */
  TOK_WAIT,  /* wait (v1.2)                  */

  /* ── Error handling ────────────────────────────────── */
  TOK_TRY,       /* try (v1.2)                   */
  TOK_ERROR_KW,  /* error (v1.2 keyword)         */
  TOK_THROW,     /* throw (v2 §13.1)             */
  TOK_ENSURE,    /* ensure (v2 §13.2)            */
  TOK_REVERT,    /* revert (v2 §13.3/§13.7)      */
  TOK_ERX,       /* erx (v2 §13.5 error reg)    */
  TOK_RESUME,    /* resume (v2 §13.7)            */
  TOK_RETRY,     /* retry (v2 §13.7)             */
  TOK_EMIT,      /* emit (v2 §13.7 log)          */
  TOK_ATOMIC_KW, /* atomic (v2 §13.7 var qual)  */

  /* ── Register / Mold (§16) ─────────────────────────── */
  TOK_REGISTER, /* register (v2 §16.1 hw reg)   */
  TOK_MOLD,     /* mold (v2 §16.6 bit-field)    */

  /* ── Type alias (v1.2) ────────────────────────────── */
  TOK_TYPE_KW, /* type (v1.2 type alias decl)  */

  /* ── Data structures ───────────────────────────────── */
  TOK_MAP_KW, /* map keyword (v1.2)           */

  /* ── System ────────────────────────────────────────── */
  TOK_CHECK_CPU, /* máy rảnh, check_cpu          */
  TOK_PATCH,     /* vá mã, patch                 */

  /* ── Arithmetic operators ──────────────────────────── */
  TOK_PLUS,    /* +                            */
  TOK_MINUS,   /* -                            */
  TOK_STAR,    /* *                            */
  TOK_SLASH,   /* /                            */
  TOK_PERCENT, /* % (v1.2: percent, not mod)   */
  TOK_POWER,   /* ^ (v1.2: power, not XOR)     */
  TOK_MOD,     /* mod (v1.2: remainder)        */

  /* ── Comparison ────────────────────────────────────── */
  TOK_EQ,      /* ==                           */
  TOK_NE,      /* !=                           */
  TOK_GT,      /* >                            */
  TOK_LT,      /* <                            */
  TOK_GE,      /* >=                           */
  TOK_LE,      /* <=                           */
  TOK_SAFE_EQ, /* ?= (v1.2 safe equal)         */
  TOK_SAFE_NE, /* ?=/= (v1.2 safe not-equal)   */

  /* ── Assignment ────────────────────────────────────── */
  TOK_ASSIGN, /* =                            */

  /* ── Logical (v1.2: & = AND, || = OR) ──────────────── */
  TOK_AND, /* & (v1.2: logical AND)        */
  TOK_OR,  /* || (v1.2: logical OR)        */
  TOK_NOT, /* ! (v1.2: logical NOT)        */

  /* ── Bitwise (v1.2: keyword operators) ─────────────── */
  TOK_BIT_AND, /* (legacy, v1.2 uses & for AND) */
  TOK_BIT_OR,  /* | (legacy)                   */
  TOK_BIT_XOR, /* xor (v1.2 keyword)           */
  TOK_BIT_SHL, /* shl (v1.2 keyword)           */
  TOK_BIT_SHR, /* shr (v1.2 keyword, >> is cast) */
  TOK_BIT_NOT, /* ~                            */

  /* ── Special operators (v1.2) ──────────────────────── */
  TOK_SAFE_ACCESS, /* ?. (safe member access)      */
  TOK_EXIST,       /* ? (existence check)          */
  TOK_CAST,        /* >> (type cast)               */
  TOK_PATTERN,     /* :~ (pattern match)           */
  TOK_HASH,        /* # (comment marker)           */

  /* ── AI / advanced operators (§26.2, §24.4) ──────── */
  TOK_MATMUL,      /* ** (matrix multiply)         */
  TOK_FMA,         /* >< (fused multiply-add)      */
  TOK_LOCK,        /* lock (atomic prefix)         */
  TOK_ATOMIC_BANG, /* !! (atomic postfix)          */

  /* ── Compound assignment ──────────────────────────── */
  TOK_PLUS_ASSIGN,  /* +=                            */
  TOK_MINUS_ASSIGN, /* -=                            */
  TOK_STAR_ASSIGN,  /* *=                            */
  TOK_SLASH_ASSIGN, /* /=                            */

  /* ── Delimiters ────────────────────────────────────── */
  TOK_LPAREN,    /* (                            */
  TOK_RPAREN,    /* )                            */
  TOK_LBRACKET,  /* [                            */
  TOK_RBRACKET,  /* ]                            */
  TOK_LBRACE,    /* {                            */
  TOK_RBRACE,    /* }                            */
  TOK_COMMA,     /* ,                            */
  TOK_DOT,       /* .                            */
  TOK_DOTDOT,    /* ..                           */
  TOK_COLON,     /* :                            */
  TOK_SEMICOLON, /* ;                            */
  TOK_ARROW,     /* ->                           */
  TOK_LARROW,    /* <-  (§23 port send)          */
  TOK_AT,        /* @   (§18 attribute)          */
  TOK_NEWLINE,   /* statement separator          */

  /* ── Module system ─────────────────────────────────── */
  TOK_IMPORT,  /* nhập_khẩu, import            */
  TOK_FROM,    /* từ, from                     */
  TOK_MODULE,  /* mô_đun, module               */
  TOK_EXPORT,  /* xuất, export                 */
  TOK_AS,      /* là, as                       */
  TOK_INCLUDE, /* bao_gồm, include             */

  /* ── Keywords (for/range) ──────────────────────────── */
  TOK_IN, /* trong, in (v1.2: param block) */

  /* ── Boolean / null literals ───────────────────────── */
  TOK_TRUE,     /* đúng, true                   */
  TOK_FALSE,    /* sai, false                   */
  TOK_NONE_LIT, /* rỗng, none                   */

  TOK_COUNT
} vir_tok_t;

/* ═══════════════════════════════════════════════════════
 * Token
 * ═══════════════════════════════════════════════════════ */

#define TOK_STR_MAX 256

typedef struct {
  vir_tok_t type;
  uint32_t line;
  uint32_t col;
  union {
    int64_t int_val;
    double float_val;
    struct {
      char buf[TOK_STR_MAX];
      uint32_t len;
    } str;
  };
} vir_token_t;

/* ═══════════════════════════════════════════════════════
 * Lexer State
 * ═══════════════════════════════════════════════════════ */

#define LEX_INIT_TOKENS 16384
#define LEX_MAX_TOKENS 262144

typedef struct {
  const char *source;
  size_t source_len;
  size_t pos;
  uint32_t line;
  uint32_t col;
  int paren_depth; /* For newline suppression         */

  vir_token_t *tokens;
  uint32_t token_count;
  uint32_t token_capacity;

  char error[256];
} vir_lexer_t;

/* ═══════════════════════════════════════════════════════
 * API
 * ═══════════════════════════════════════════════════════ */

void lexer_init(vir_lexer_t *lex, const char *source, size_t len);
void lexer_free(vir_lexer_t *lex);
int lexer_tokenize(vir_lexer_t *lex);
const char *lexer_token_name(vir_tok_t type);

/* §28.3 Dynamic keyword registry — register a custom keyword at runtime
 * that maps the given word (UTF-8) to the given token type. Returns 0 on
 * success, nonzero on overflow. Use this to add keyword aliases for
 * additional natural languages (SubLib adapters). */
int vir_register_keyword(const char *word, vir_tok_t type);
int vir_register_multi_keyword(const char *w1, const char *w2, const char *w3,
                               vir_tok_t type);
int vir_register_stop_word(const char *word);

/* §28 SubLib Adapter — call once at startup to register all CJK and
 * Vietnamese keyword aliases. Defined in sublib_adapter.c. */
void vir_sublib_adapter_init(void);

#ifdef __cplusplus
}
#endif

#endif /* VIR_LEXER_H */
