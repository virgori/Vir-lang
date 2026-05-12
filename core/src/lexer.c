/*
 * lexer.c – Vir Source Lexer Implementation
 * ==========================================
 * UTF-8 tokenizer with Vietnamese + English keyword support.
 * Multi-word Vietnamese keywords handled via lookahead.
 */

#include "lexer.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════
 * UTF-8 Helpers
 * ═══════════════════════════════════════════════════════ */

/* Any byte with high bit set is part of a multi-byte UTF-8 char */
static int is_word_char(unsigned char c) {
  return isalnum(c) || c == '_' || (c >= 0x80);
}

static int is_digit_char(unsigned char c) { return (c >= '0' && c <= '9'); }

/* ═══════════════════════════════════════════════════════
 * Keyword Table (single-word)
 * ═══════════════════════════════════════════════════════ */

typedef struct {
  const char *word;
  vir_tok_t type;
} kw_single_t;

static const kw_single_t kw_singles[] = {
    /* Vietnamese single-word */
    {"hàm", TOK_FUNC},
    {"biến", TOK_VAR},
    {"hằng", TOK_CONST},
    {"nếu", TOK_IF},
    {"lặp", TOK_LOOP},
    {"thì", TOK_THEN},
    {"hết", TOK_END},
    {"nhập", TOK_INPUT},
    {"đúng", TOK_TRUE},
    {"sai", TOK_FALSE},
    {"rỗng", TOK_NONE_LIT},
    {"cộng", TOK_PLUS},
    {"trừ", TOK_MINUS},
    {"nhân", TOK_STAR},
    {"chia", TOK_SLASH},
    {"bằng", TOK_EQ},
    {"khác", TOK_NE},
    {"và", TOK_AND},
    {"hoặc", TOK_OR},
    {"thoát", TOK_BREAK},
    {"bản_ghi", TOK_RECORD},
    {"liệt_kê", TOK_ENUM},
    {"trong", TOK_IN},

    /* Vietnamese module keywords */
    {"nhập_khẩu", TOK_IMPORT},
    {"từ", TOK_FROM},
    {"mô_đun", TOK_MODULE},
    {"xuất", TOK_EXPORT},
    {"bao_gồm", TOK_INCLUDE},

    /* English */
    {"func", TOK_FUNC},
    {"function", TOK_FUNC},
    {"var", TOK_VAR},
    {"let", TOK_VAR},
    {"const", TOK_CONST},
    {"if", TOK_IF},
    {"else", TOK_ELSE},
    {"elif", TOK_ELIF},
    {"eif", TOK_EIF},
    {"loop", TOK_LOOP},
    {"while", TOK_WHILE},
    {"when", TOK_WHEN},
    {"for", TOK_FOR},
    {"break", TOK_BREAK},
    {"continue", TOK_CONTINUE},
    {"skip", TOK_SKIP},
    {"return", TOK_RETURN},
    {"out", TOK_OUT},
    {"case", TOK_CASE},
    {"del", TOK_DEL},
    {"xóa", TOK_DEL},
    {"then", TOK_THEN},
    {"do", TOK_THEN},
    {"end", TOK_END},
    {"print", TOK_PRINT},
    {"input", TOK_INPUT},
    {"check_cpu", TOK_CHECK_CPU},
    {"patch", TOK_PATCH},
    {"true", TOK_TRUE},
    {"false", TOK_FALSE},
    {"none", TOK_NONE_LIT},
    {"and", TOK_AND},
    {"or", TOK_OR},
    {"not", TOK_NOT},
    {"record", TOK_RECORD},
    {"struct", TOK_RECORD},
    {"enum", TOK_ENUM},
    {"entity", TOK_ENTITY},
    {"method", TOK_METHOD},
    {"class", TOK_CLASS},
    {"this", TOK_THIS},
    {"has", TOK_HAS},
    {"share", TOK_SHARE},
    {"get", TOK_GET},
    {"async", TOK_ASYNC},
    {"task", TOK_TASK},
    {"wait", TOK_WAIT},
    {"try", TOK_TRY},
    {"error", TOK_ERROR_KW},
    {"throw", TOK_THROW},
    {"ensure", TOK_ENSURE},
    {"revert", TOK_REVERT},
    {"erx", TOK_ERX},
    {"resume", TOK_RESUME},
    {"retry", TOK_RETRY},
    {"emit", TOK_EMIT},
    {"atomic", TOK_ATOMIC_KW},
    {"register", TOK_REGISTER},
    {"mold", TOK_MOLD},
    {"map", TOK_MAP_KW},
    {"mod", TOK_MOD},
    {"xor", TOK_BIT_XOR},
    {"shl", TOK_BIT_SHL},
    {"shr", TOK_BIT_SHR},
    {"in", TOK_IN},
    {"import", TOK_IMPORT},
    {"from", TOK_FROM},
    {"module", TOK_MODULE},
    {"export", TOK_EXPORT},
    {"as", TOK_AS},
    {"include", TOK_INCLUDE},
    {"type", TOK_TYPE_KW},
    {"lock", TOK_LOCK},

    /* §28 CJK keyword aliases — Chinese, Japanese, Korean.
     * Minimal subset covering core control-flow and declarations. */
    /* 中文 (Simplified Chinese) */
    {"函数", TOK_FUNC},
    {"变量", TOK_VAR},
    {"常量", TOK_CONST},
    {"如果", TOK_IF},
    {"否则", TOK_ELSE},
    {"循环", TOK_LOOP},
    {"结束", TOK_END},
    {"返回", TOK_RETURN},
    {"真", TOK_TRUE},
    {"假", TOK_FALSE},
    {"空", TOK_NONE_LIT},
    {"打印", TOK_PRINT},
    {"输入", TOK_INPUT},
    {"导入", TOK_IMPORT},
    {"导出", TOK_EXPORT},
    {"模块", TOK_MODULE},
    {"包含", TOK_INCLUDE},
    {"跳出", TOK_BREAK},
    {"继续", TOK_CONTINUE},
    {"与", TOK_AND},
    {"或", TOK_OR},
    {"非", TOK_NOT},
    /* 日本語 (Japanese) */
    {"関数", TOK_FUNC},
    {"変数", TOK_VAR},
    {"定数", TOK_CONST},
    {"もし", TOK_IF},
    {"他ならば", TOK_ELIF},
    {"そうでなければ", TOK_ELSE},
    {"繰り返し", TOK_LOOP},
    {"終わり", TOK_END},
    {"戻る", TOK_RETURN},
    {"出力", TOK_OUT},
    {"真", TOK_TRUE},
    {"偽", TOK_FALSE},
    {"印刷", TOK_PRINT},
    {"入力", TOK_INPUT},
    {"読込", TOK_IMPORT},
    {"書出", TOK_EXPORT},
    {"モジュール", TOK_MODULE},
    {"含む", TOK_INCLUDE},
    {"抜ける", TOK_BREAK},
    {"続ける", TOK_CONTINUE},
    {"且つ", TOK_AND},
    {"又は", TOK_OR},
    {"否", TOK_NOT},

    /* 한국어 (Korean) */
    {"함수", TOK_FUNC},
    {"변수", TOK_VAR},
    {"상수", TOK_CONST},
    {"만약", TOK_IF},
    {"그외만약", TOK_ELIF},
    {"아니면", TOK_ELSE},
    {"반복", TOK_LOOP},
    {"끝", TOK_END},
    {"반환", TOK_RETURN},
    {"출력", TOK_OUT},
    {"참", TOK_TRUE},
    {"거짓", TOK_FALSE},
    {"인쇄", TOK_PRINT},
    {"입력", TOK_INPUT},
    {"가져오기", TOK_IMPORT},
    {"내보내기", TOK_EXPORT},
    {"모듈", TOK_MODULE},
    {"포함", TOK_INCLUDE},
    {"탈출", TOK_BREAK},
    {"계속", TOK_CONTINUE},
    {"그리고", TOK_AND},
    {"또는", TOK_OR},
    {"아님", TOK_NOT},
    {NULL, TOK_EOF}};

/* ═══════════════════════════════════════════════════════
 * Multi-word Keyword Table (Vietnamese)
 * ═══════════════════════════════════════════════════════
 * Two- and three-word Vietnamese keywords.  After reading
 * the first word, we peek ahead to try matching.
 */

typedef struct {
  const char *w1;
  const char *w2;
  const char *w3; /* NULL if two-word */
  vir_tok_t type;
} kw_multi_t;

static const kw_multi_t kw_multis[] = {
    /* 3-word first (greedy match) */
    {"ta", "có", "hàm", TOK_FUNC},        {"cho", "biến", NULL, TOK_VAR},
    {"đặt", "biến", NULL, TOK_VAR},       {"ngược", "lại", NULL, TOK_ELSE},
    {"còn", "nếu", NULL, TOK_ELIF},       {"nếu", "không", NULL, TOK_ELSE},
    {"trả", "về", NULL, TOK_RETURN},      {"in", "ra", NULL, TOK_PRINT},
    {"nhập", "vào", NULL, TOK_INPUT},     {"trong", "khi", NULL, TOK_WHILE},
    {"với", "mỗi", NULL, TOK_FOR},        {"thoát", "vòng", NULL, TOK_BREAK},
    {"bỏ", "qua", NULL, TOK_CONTINUE},    {"tiếp", "tục", NULL, TOK_CONTINUE},
    {"máy", "rảnh", NULL, TOK_CHECK_CPU}, {"vá", "mã", NULL, TOK_PATCH},
    {"lớn", "hơn", NULL, TOK_GT},         {"nhỏ", "hơn", NULL, TOK_LT},
    {"chia", "dư", NULL, TOK_PERCENT},    {NULL, NULL, NULL, TOK_EOF}};

/* ═══════════════════════════════════════════════════════
 * Vietnamese stop words (ignored during tokenization)
 * ═══════════════════════════════════════════════════════ */

static const char *stop_words[] = {
    "là",  "nhé",  "giúp", "ơi",  "đi",  "nào",  "được",  "cái", "này", "kia",
    "đó",  "ấy",   "mà",   "rồi", "vậy", "thôi", "hãy",   "xin", "tôi", "bạn",
    "của", "cùng", "để",   "ra",  "vào", "lên",  "xuống", NULL};

static int is_stop_word(const char *word) {
  for (int i = 0; stop_words[i]; i++) {
    if (strcmp(word, stop_words[i]) == 0)
      return 1;
  }
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Lexer Internal Helpers
 * ═══════════════════════════════════════════════════════ */

static inline int lex_eof(const vir_lexer_t *lex) {
  return lex->pos >= lex->source_len;
}

static inline unsigned char lex_peek(const vir_lexer_t *lex) {
  if (lex->pos < lex->source_len)
    return (unsigned char)lex->source[lex->pos];
  return 0;
}

static inline unsigned char lex_peek_at(const vir_lexer_t *lex, size_t off) {
  size_t p = lex->pos + off;
  if (p < lex->source_len)
    return (unsigned char)lex->source[p];
  return 0;
}

static inline unsigned char lex_advance(vir_lexer_t *lex) {
  unsigned char c = lex_peek(lex);
  if (c == '\n') {
    lex->line++;
    lex->col = 1;
  } else {
    lex->col++;
  }
  lex->pos++;
  return c;
}

static void lex_skip_whitespace(vir_lexer_t *lex) {
  while (!lex_eof(lex)) {
    unsigned char c = lex_peek(lex);
    if (c == ' ' || c == '\t' || c == '\r') {
      lex_advance(lex);
    } else {
      break;
    }
  }
}

static void lex_skip_comment(vir_lexer_t *lex) {
  /* # ... until end of line */
  while (!lex_eof(lex) && lex_peek(lex) != '\n')
    lex_advance(lex);
}

/* Read a word (identifier-like) into buf, return length */
static size_t lex_read_word(vir_lexer_t *lex, char *buf, size_t buf_sz) {
  size_t n = 0;
  while (!lex_eof(lex) && is_word_char(lex_peek(lex)) && n < buf_sz - 1) {
    buf[n++] = (char)lex_advance(lex);
  }
  buf[n] = '\0';
  return n;
}

/* Save / restore position for lookahead */
typedef struct {
  size_t pos;
  uint32_t line;
  uint32_t col;
} lex_savepoint_t;

static lex_savepoint_t lex_save(const vir_lexer_t *lex) {
  return (lex_savepoint_t){lex->pos, lex->line, lex->col};
}

static void lex_restore(vir_lexer_t *lex, lex_savepoint_t sp) {
  lex->pos = sp.pos;
  lex->line = sp.line;
  lex->col = sp.col;
}

/* Try to add a token */
static int lex_push_token(vir_lexer_t *lex, vir_token_t tok) {
  if (lex->token_count >= LEX_MAX_TOKENS) {
    snprintf(lex->error, sizeof(lex->error), "too many tokens");
    return -1;
  }
  if (lex->token_count >= lex->token_capacity) {
    uint32_t new_cap = lex->token_capacity * 2;
    if (new_cap > LEX_MAX_TOKENS)
      new_cap = LEX_MAX_TOKENS;
    vir_token_t *new_buf =
        (vir_token_t *)realloc(lex->tokens, new_cap * sizeof(vir_token_t));
    if (!new_buf) {
      snprintf(lex->error, sizeof(lex->error), "token alloc failed");
      return -1;
    }
    lex->tokens = new_buf;
    lex->token_capacity = new_cap;
  }
  lex->tokens[lex->token_count++] = tok;
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Single-word keyword lookup
 * ═══════════════════════════════════════════════════════ */

/* §28.3 Dynamic keyword registry — populated at runtime via
 * vir_register_keyword(). Looked up after the static table. */
#define VIR_KW_REGISTRY_MAX 256
static struct {
  char word[64];
  vir_tok_t type;
} g_kw_registry[VIR_KW_REGISTRY_MAX];
static uint32_t g_kw_registry_count = 0;

int vir_register_keyword(const char *word, vir_tok_t type) {
  if (!word)
    return -1;
  if (g_kw_registry_count >= VIR_KW_REGISTRY_MAX)
    return -1;
  /* De-dup: replace if already registered. */
  for (uint32_t i = 0; i < g_kw_registry_count; i++) {
    if (strcmp(g_kw_registry[i].word, word) == 0) {
      g_kw_registry[i].type = type;
      return 0;
    }
  }
  strncpy(g_kw_registry[g_kw_registry_count].word, word,
          sizeof(g_kw_registry[0].word) - 1);
  g_kw_registry[g_kw_registry_count].word[sizeof(g_kw_registry[0].word) - 1] =
      '\0';
  g_kw_registry[g_kw_registry_count].type = type;
  g_kw_registry_count++;
  return 0;
}

/* §28.3 Dynamic multi-word keyword registry */
#define VIR_MULTI_REGISTRY_MAX 64
static struct {
  char w1[48];
  char w2[48];
  char w3[48]; /* empty string = two-word only */
  vir_tok_t type;
} g_multi_registry[VIR_MULTI_REGISTRY_MAX];
static uint32_t g_multi_registry_count = 0;

int vir_register_multi_keyword(const char *w1, const char *w2, const char *w3,
                               vir_tok_t type) {
  if (!w1 || !w2)
    return -1;
  if (g_multi_registry_count >= VIR_MULTI_REGISTRY_MAX)
    return -1;
  /* De-dup */
  for (uint32_t i = 0; i < g_multi_registry_count; i++) {
    if (strcmp(g_multi_registry[i].w1, w1) == 0 &&
        strcmp(g_multi_registry[i].w2, w2) == 0) {
      g_multi_registry[i].type = type;
      return 0;
    }
  }
  strncpy(g_multi_registry[g_multi_registry_count].w1, w1, 47);
  g_multi_registry[g_multi_registry_count].w1[47] = '\0';
  strncpy(g_multi_registry[g_multi_registry_count].w2, w2, 47);
  g_multi_registry[g_multi_registry_count].w2[47] = '\0';
  if (w3) {
    strncpy(g_multi_registry[g_multi_registry_count].w3, w3, 47);
    g_multi_registry[g_multi_registry_count].w3[47] = '\0';
  } else {
    g_multi_registry[g_multi_registry_count].w3[0] = '\0';
  }
  g_multi_registry[g_multi_registry_count].type = type;
  g_multi_registry_count++;
  return 0;
}

/* §28.3 Dynamic stop-word registry */
#define VIR_STOP_REGISTRY_MAX 64
static char g_stop_registry[VIR_STOP_REGISTRY_MAX][48];
static uint32_t g_stop_registry_count = 0;

int vir_register_stop_word(const char *word) {
  if (!word)
    return -1;
  if (g_stop_registry_count >= VIR_STOP_REGISTRY_MAX)
    return -1;
  for (uint32_t i = 0; i < g_stop_registry_count; i++) {
    if (strcmp(g_stop_registry[i], word) == 0)
      return 0; /* already registered */
  }
  strncpy(g_stop_registry[g_stop_registry_count], word, 47);
  g_stop_registry[g_stop_registry_count][47] = '\0';
  g_stop_registry_count++;
  return 0;
}

static vir_tok_t lookup_single(const char *word) {
  for (int i = 0; kw_singles[i].word; i++) {
    if (strcmp(kw_singles[i].word, word) == 0)
      return kw_singles[i].type;
  }
  /* §28.3 Fall through to dynamic registry. */
  for (uint32_t i = 0; i < g_kw_registry_count; i++) {
    if (strcmp(g_kw_registry[i].word, word) == 0)
      return g_kw_registry[i].type;
  }
  return TOK_EOF; /* not found */
}

/* ═══════════════════════════════════════════════════════
 * Multi-word keyword lookahead
 * ═══════════════════════════════════════════════════════
 * Given the first word, peek ahead to match 2- or 3-word
 * Vietnamese keywords.  Returns TOK_EOF if no match.
 */

static vir_tok_t try_multi_keyword(vir_lexer_t *lex, const char *w1) {
/* Helper: attempt to match w2 (and optionally w3) from current position.
 * Returns matched type or TOK_EOF; restores position on failure. */
#define TRY_MULTI_MATCH(need_w2, need_w3, result_type)                         \
  do {                                                                         \
    lex_savepoint_t _sp = lex_save(lex);                                       \
    lex_skip_whitespace(lex);                                                  \
    char _w2[TOK_STR_MAX];                                                     \
    if (lex_eof(lex) || !is_word_char(lex_peek(lex))) {                        \
      lex_restore(lex, _sp);                                                   \
      break;                                                                   \
    }                                                                          \
    lex_read_word(lex, _w2, sizeof(_w2));                                      \
    if (strcmp((need_w2), _w2) != 0) {                                         \
      lex_restore(lex, _sp);                                                   \
      break;                                                                   \
    }                                                                          \
    if ((need_w3) && (need_w3)[0] != '\0') {                                   \
      lex_savepoint_t _sp3 = lex_save(lex);                                    \
      lex_skip_whitespace(lex);                                                \
      char _w3[TOK_STR_MAX];                                                   \
      if (lex_eof(lex) || !is_word_char(lex_peek(lex))) {                      \
        lex_restore(lex, _sp);                                                 \
        break;                                                                 \
      }                                                                        \
      lex_read_word(lex, _w3, sizeof(_w3));                                    \
      if (strcmp((need_w3), _w3) != 0) {                                       \
        lex_restore(lex, _sp);                                                 \
        break;                                                                 \
      }                                                                        \
      (void)_sp3;                                                              \
    }                                                                          \
    return (result_type);                                                      \
  } while (0)

  /* Static multi-word table */
  for (int i = 0; kw_multis[i].w1; i++) {
    if (strcmp(kw_multis[i].w1, w1) != 0)
      continue;
    TRY_MULTI_MATCH(kw_multis[i].w2, kw_multis[i].w3, kw_multis[i].type);
  }

  /* §28.3 Dynamic multi-word registry */
  for (uint32_t i = 0; i < g_multi_registry_count; i++) {
    if (strcmp(g_multi_registry[i].w1, w1) != 0)
      continue;
    TRY_MULTI_MATCH(g_multi_registry[i].w2,
                    g_multi_registry[i].w3[0] ? g_multi_registry[i].w3 : NULL,
                    g_multi_registry[i].type);
  }

#undef TRY_MULTI_MATCH
  return TOK_EOF; /* no multi-word match */
}

/* ═══════════════════════════════════════════════════════
 * Number Lexing
 * ═══════════════════════════════════════════════════════ */

static int lex_number(vir_lexer_t *lex, vir_token_t *tok) {
  tok->type = TOK_INT;
  tok->line = lex->line;
  tok->col = lex->col;

  char buf[64];
  size_t n = 0;
  int is_float = 0;

  /* Hex? */
  if (lex_peek(lex) == '0' &&
      (lex_peek_at(lex, 1) == 'x' || lex_peek_at(lex, 1) == 'X')) {
    buf[n++] = (char)lex_advance(lex); /* 0 */
    buf[n++] = (char)lex_advance(lex); /* x */
    while (!lex_eof(lex) && isxdigit(lex_peek(lex)) && n < sizeof(buf) - 1)
      buf[n++] = (char)lex_advance(lex);
    buf[n] = '\0';
    tok->int_val = strtoll(buf, NULL, 16);
    return 0;
  }

  /* Octal? (0o755 format) */
  if (lex_peek(lex) == '0' &&
      (lex_peek_at(lex, 1) == 'o' || lex_peek_at(lex, 1) == 'O')) {
    buf[n++] = (char)lex_advance(lex); /* 0 */
    buf[n++] = (char)lex_advance(lex); /* o */
    while (!lex_eof(lex) && lex_peek(lex) >= '0' && lex_peek(lex) <= '7' &&
           n < sizeof(buf) - 1)
      buf[n++] = (char)lex_advance(lex);
    buf[n] = '\0';
    tok->int_val = strtoll(buf + 2, NULL, 8); /* skip "0o" prefix */
    return 0;
  }

  while (!lex_eof(lex) &&
         (is_digit_char(lex_peek(lex)) || lex_peek(lex) == '.') &&
         n < sizeof(buf) - 1) {
    if (lex_peek(lex) == '.') {
      if (is_float)
        break; /* second dot = stop */
      /* Check for '..' range operator — don't consume as decimal */
      if (lex_peek_at(lex, 1) == '.')
        break;
      /* §11 UFCS: `10.foo()` — don't swallow '.' if followed by an
       * identifier-start character (letter or '_').  This lets
       * integer literals participate in method call chains. */
      {
        int nx = lex_peek_at(lex, 1);
        if (isalpha(nx) || nx == '_')
          break;
      }
      is_float = 1;
    }
    buf[n++] = (char)lex_advance(lex);
  }
  buf[n] = '\0';

  if (is_float) {
    tok->type = TOK_FLOAT;
    tok->float_val = strtod(buf, NULL);
  } else {
    tok->int_val = strtoll(buf, NULL, 10);
  }
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * String Lexing
 * ═══════════════════════════════════════════════════════ */

static int lex_string(vir_lexer_t *lex, vir_token_t *tok) {
  tok->type = TOK_STRING;
  tok->line = lex->line;
  tok->col = lex->col;

  char quote = (char)lex_advance(lex); /* consume opening ' or " */
  size_t n = 0;

  while (!lex_eof(lex) && lex_peek(lex) != (unsigned char)quote) {
    if (lex_peek(lex) == '\\') {
      lex_advance(lex); /* skip backslash */
      if (lex_eof(lex))
        break;
      char esc = (char)lex_advance(lex);
      switch (esc) {
      case 'n':
        if (n < TOK_STR_MAX - 1)
          tok->str.buf[n++] = '\n';
        break;
      case 't':
        if (n < TOK_STR_MAX - 1)
          tok->str.buf[n++] = '\t';
        break;
      case '\\':
        if (n < TOK_STR_MAX - 1)
          tok->str.buf[n++] = '\\';
        break;
      case '"':
        if (n < TOK_STR_MAX - 1)
          tok->str.buf[n++] = '"';
        break;
      case '\'':
        if (n < TOK_STR_MAX - 1)
          tok->str.buf[n++] = '\'';
        break;
      default:
        if (n < TOK_STR_MAX - 1)
          tok->str.buf[n++] = esc;
        break;
      }
    } else if (lex_peek(lex) == '$') {
      /* String interpolation: $identifier */
      /* Mark the position where interpolation starts */
      if (n < TOK_STR_MAX - 1)
        tok->str.buf[n++] = '\x01'; /* Use \x01 as interpolation marker */
      lex_advance(lex);             /* consume $ */

      /* Read the identifier name */
      while (!lex_eof(lex) &&
             (isalnum(lex_peek(lex)) || lex_peek(lex) == '_')) {
        if (n < TOK_STR_MAX - 1)
          tok->str.buf[n++] = (char)lex_advance(lex);
        else
          lex_advance(lex); /* overflow: skip */
      }

      /* Mark the end of interpolation */
      if (n < TOK_STR_MAX - 1)
        tok->str.buf[n++] = '\x02'; /* Use \x02 as end marker */
    } else {
      if (n < TOK_STR_MAX - 1)
        tok->str.buf[n++] = (char)lex_advance(lex);
      else
        lex_advance(lex); /* overflow: skip */
    }
  }

  if (!lex_eof(lex))
    lex_advance(lex); /* consume closing quote */
  tok->str.buf[n] = '\0';
  tok->str.len = (uint32_t)n;
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Word / Keyword Lexing
 * ═══════════════════════════════════════════════════════ */

static int lex_word(vir_lexer_t *lex, vir_token_t *tok) {
  uint32_t start_line = lex->line;
  uint32_t start_col = lex->col;

  char word[TOK_STR_MAX];
  lex_read_word(lex, word, sizeof(word));

  tok->line = start_line;
  tok->col = start_col;
  strncpy(tok->str.buf, word, TOK_STR_MAX - 1);
  tok->str.buf[TOK_STR_MAX - 1] = '\0';
  tok->str.len = (uint32_t)strlen(tok->str.buf);

  /* Try multi-word keyword first (greedy) */
  vir_tok_t multi = try_multi_keyword(lex, word);
  if (multi != TOK_EOF) {
    tok->type = multi;
    return 0;
  }

  /* Try single-word keyword */
  vir_tok_t single = lookup_single(word);
  if (single != TOK_EOF) {
    tok->type = single;
    return 0;
  }

  /* Stop word → skip it (return 1 to signal "no token emitted") */
  if (is_stop_word(word)) {
    return 1; /* caller skips */
  }
  /* §28.3 Dynamic stop-word registry */
  for (uint32_t i = 0; i < g_stop_registry_count; i++) {
    if (strcmp(g_stop_registry[i], word) == 0)
      return 1;
  }

  /* Identifier */
  tok->type = TOK_IDENT;
  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Main Tokenize Loop
 * ═══════════════════════════════════════════════════════ */

void lexer_init(vir_lexer_t *lex, const char *source, size_t len) {
  memset(lex, 0, sizeof(*lex));
  lex->source = source;
  lex->source_len = len;
  lex->line = 1;
  lex->col = 1;
  lex->token_capacity = LEX_INIT_TOKENS;
  lex->tokens =
      (vir_token_t *)malloc(lex->token_capacity * sizeof(vir_token_t));
}

void lexer_free(vir_lexer_t *lex) {
  if (lex && lex->tokens) {
    free(lex->tokens);
    lex->tokens = NULL;
  }
}

int lexer_tokenize(vir_lexer_t *lex) {
  int prev_was_newline = 1; /* Suppress leading newlines */

  while (!lex_eof(lex)) {
    lex_skip_whitespace(lex);
    if (lex_eof(lex))
      break;

    unsigned char c = lex_peek(lex);

    /* ── Newline (statement separator) ──────────────── */
    if (c == '\n') {
      lex_advance(lex);
      /* Collapse multiple newlines, suppress inside parens */
      if (!prev_was_newline && lex->paren_depth == 0) {
        vir_token_t tok = {0};
        tok.type = TOK_NEWLINE;
        tok.line = lex->line;
        tok.col = lex->col;
        lex_push_token(lex, tok);
        prev_was_newline = 1;
      }
      continue;
    }

    prev_was_newline = 0;

    /* ── Comment ────────────────────────────────────── */
    if (c == '#') {
      /* ## block comment ## */
      if (lex_peek_at(lex, 1) == '#') {
        lex_advance(lex);
        lex_advance(lex); /* consume ## */
        while (!lex_eof(lex)) {
          if (lex_peek(lex) == '#' && lex_peek_at(lex, 1) == '#') {
            lex_advance(lex);
            lex_advance(lex);
            break;
          }
          lex_advance(lex);
        }
      } else {
        lex_skip_comment(lex);
      }
      continue;
    }

    /* ── String literal ─────────────────────────────── */
    if (c == '"' || c == '\'') {
      vir_token_t tok = {0};
      lex_string(lex, &tok);
      lex_push_token(lex, tok);
      continue;
    }

    /* ── Number literal ─────────────────────────────── */
    if (is_digit_char(c)) {
      vir_token_t tok = {0};
      lex_number(lex, &tok);
      lex_push_token(lex, tok);
      continue;
    }

    /* ── Multi-char operators (v1.2) ────────────────── */
    unsigned char c2 = lex_peek_at(lex, 1);

    if (c == '=' && c2 == '=') {
      vir_token_t tok = {TOK_EQ, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '!' && c2 == '=') {
      vir_token_t tok = {TOK_NE, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '>' && c2 == '=') {
      vir_token_t tok = {TOK_GE, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '<' && c2 == '=') {
      vir_token_t tok = {TOK_LE, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* v1.2: ?=/= (safe not-equal, 4 chars) — check before ?= */
    if (c == '?' && c2 == '=' && lex_peek_at(lex, 2) == '/' &&
        lex_peek_at(lex, 3) == '=') {
      vir_token_t tok = {TOK_SAFE_NE, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* v1.2: ?= (safe equal) */
    if (c == '?' && c2 == '=') {
      vir_token_t tok = {TOK_SAFE_EQ, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* v1.2: ?. (safe member access) */
    if (c == '?' && c2 == '.') {
      vir_token_t tok = {TOK_SAFE_ACCESS, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* v1.2: :~ (pattern match) */
    if (c == ':' && c2 == '~') {
      vir_token_t tok = {TOK_PATTERN, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '|' && c2 == '|') {
      vir_token_t tok = {TOK_OR, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '-' && c2 == '>') {
      vir_token_t tok = {TOK_ARROW, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* §23.2 `<-` port send arrow */
    if (c == '<' && c2 == '-') {
      vir_token_t tok = {TOK_LARROW, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '<' && c2 == '<') {
      vir_token_t tok = {TOK_BIT_SHL, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* v1.2: >> is cast (not bit shift right) */
    if (c == '>' && c2 == '>') {
      vir_token_t tok = {TOK_CAST, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* §26.2: ** matmul */
    if (c == '*' && c2 == '*') {
      vir_token_t tok = {TOK_MATMUL, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* §26.2: >< fused multiply-add */
    if (c == '>' && c2 == '<') {
      vir_token_t tok = {TOK_FMA, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* §24.4: !! atomic postfix */
    if (c == '!' && c2 == '!') {
      vir_token_t tok = {TOK_ATOMIC_BANG, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    /* Compound assignment: += -= *= /= */
    if (c == '+' && c2 == '=') {
      vir_token_t tok = {TOK_PLUS_ASSIGN, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '-' && c2 == '=') {
      vir_token_t tok = {TOK_MINUS_ASSIGN, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '*' && c2 == '=') {
      vir_token_t tok = {TOK_STAR_ASSIGN, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '/' && c2 == '=') {
      vir_token_t tok = {TOK_SLASH_ASSIGN, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }
    if (c == '.' && c2 == '.') {
      vir_token_t tok = {TOK_DOTDOT, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }

    /* ── Single-char operators / delimiters ─────────── */
    vir_tok_t single_sym = TOK_EOF;
    switch (c) {
    case '+':
      single_sym = TOK_PLUS;
      break;
    case '-':
      single_sym = TOK_MINUS;
      break;
    case '*':
      single_sym = TOK_STAR;
      break;
    case '/':
      single_sym = TOK_SLASH;
      break;
    case '%':
      single_sym = TOK_PERCENT;
      break;
    case '^':
      single_sym = TOK_POWER;
      break; /* v1.2: power (not XOR) */
    case '=':
      single_sym = TOK_ASSIGN;
      break;
    case '>':
      single_sym = TOK_GT;
      break;
    case '<':
      single_sym = TOK_LT;
      break;
    case '!':
      single_sym = TOK_NOT;
      break;
    case '?':
      single_sym = TOK_EXIST;
      break; /* v1.2: existence check */
    case '(':
      single_sym = TOK_LPAREN;
      lex->paren_depth++;
      break;
    case ')':
      single_sym = TOK_RPAREN;
      if (lex->paren_depth > 0)
        lex->paren_depth--;
      break;
    case '[':
      single_sym = TOK_LBRACKET;
      lex->paren_depth++;
      break;
    case ']':
      single_sym = TOK_RBRACKET;
      if (lex->paren_depth > 0)
        lex->paren_depth--;
      break;
    case '{':
      single_sym = TOK_LBRACE;
      lex->paren_depth++;
      break;
    case '}':
      single_sym = TOK_RBRACE;
      if (lex->paren_depth > 0)
        lex->paren_depth--;
      break;
    case ',':
      single_sym = TOK_COMMA;
      break;
    case '.':
      single_sym = TOK_DOT;
      break;
    case ':':
      single_sym = TOK_COLON;
      break;
    case ';':
      single_sym = TOK_SEMICOLON;
      break;
    case '&':
      single_sym = TOK_AND;
      break; /* v1.2: & is logical AND */
    case '|':
      single_sym = TOK_BIT_OR;
      break;
    case '~':
      single_sym = TOK_BIT_NOT;
      break;
    case '@':
      single_sym = TOK_AT;
      break; /* §18 @entry attribute */
    default:
      break;
    }

    if (single_sym != TOK_EOF) {
      vir_token_t tok = {single_sym, lex->line, lex->col, {0}};
      lex_advance(lex);
      lex_push_token(lex, tok);
      continue;
    }

    /* ── Word (keyword / identifier) ────────────────── */
    if (is_word_char(c)) {
      vir_token_t tok = {0};
      int rc = lex_word(lex, &tok);
      if (rc == 0) {
        lex_push_token(lex, tok);
      }
      continue;
    }

    /* unknown character — skip */
    lex_advance(lex);
  }

  /* ── Push sentinel TOK_EOF ──────────────────────────── */
  {
    vir_token_t eof_tok = {0};
    eof_tok.type = TOK_EOF;
    eof_tok.line = lex->line;
    eof_tok.col = lex->col;
    lex_push_token(lex, eof_tok);
  }

  return 0;
}

/* ═══════════════════════════════════════════════════════
 * Token Name (debug / error messages)
 * ═══════════════════════════════════════════════════════ */

const char *lexer_token_name(vir_tok_t type) {
  static const char *names[TOK_COUNT] = {
      [TOK_EOF] = "EOF",
      [TOK_ERROR] = "ERROR",
      [TOK_INT] = "INT",
      [TOK_FLOAT] = "FLOAT",
      [TOK_STRING] = "STRING",
      [TOK_IDENT] = "IDENT",
      [TOK_FUNC] = "FUNC",
      [TOK_VAR] = "VAR",
      [TOK_CONST] = "CONST",
      [TOK_IF] = "IF",
      [TOK_ELSE] = "ELSE",
      [TOK_ELIF] = "ELIF",
      [TOK_EIF] = "EIF",
      [TOK_LOOP] = "LOOP",
      [TOK_WHILE] = "WHILE",
      [TOK_WHEN] = "WHEN",
      [TOK_FOR] = "FOR",
      [TOK_BREAK] = "BREAK",
      [TOK_CONTINUE] = "CONTINUE",
      [TOK_SKIP] = "SKIP",
      [TOK_RETURN] = "RETURN",
      [TOK_OUT] = "OUT",
      [TOK_CASE] = "CASE",
      [TOK_DEL] = "DEL",
      [TOK_THEN] = "THEN",
      [TOK_END] = "END",
      [TOK_PRINT] = "PRINT",
      [TOK_INPUT] = "INPUT",
      [TOK_RECORD] = "RECORD",
      [TOK_ENUM] = "ENUM",
      [TOK_ENTITY] = "ENTITY",
      [TOK_METHOD] = "METHOD",
      [TOK_CLASS] = "CLASS",
      [TOK_THIS] = "THIS",
      [TOK_HAS] = "HAS",
      [TOK_SHARE] = "SHARE",
      [TOK_GET] = "GET",
      [TOK_ASYNC] = "ASYNC",
      [TOK_TASK] = "TASK",
      [TOK_WAIT] = "WAIT",
      [TOK_TRY] = "TRY",
      [TOK_ERROR_KW] = "ERROR",
      [TOK_THROW] = "THROW",
      [TOK_ENSURE] = "ENSURE",
      [TOK_REVERT] = "REVERT",
      [TOK_ERX] = "ERX",
      [TOK_RESUME] = "RESUME",
      [TOK_RETRY] = "RETRY",
      [TOK_EMIT] = "EMIT",
      [TOK_ATOMIC_KW] = "ATOMIC",
      [TOK_REGISTER] = "REGISTER",
      [TOK_MOLD] = "MOLD",
      [TOK_PLUS] = "PLUS",
      [TOK_MINUS] = "MINUS",
      [TOK_STAR] = "STAR",
      [TOK_SLASH] = "SLASH",
      [TOK_PERCENT] = "PERCENT",
      [TOK_POWER] = "POWER",
      [TOK_MOD] = "MOD",
      [TOK_EQ] = "EQ",
      [TOK_NE] = "NE",
      [TOK_GT] = "GT",
      [TOK_LT] = "LT",
      [TOK_GE] = "GE",
      [TOK_LE] = "LE",
      [TOK_SAFE_EQ] = "SAFE_EQ",
      [TOK_SAFE_NE] = "SAFE_NE",
      [TOK_ASSIGN] = "ASSIGN",
      [TOK_AND] = "AND",
      [TOK_OR] = "OR",
      [TOK_NOT] = "NOT",
      [TOK_BIT_AND] = "BIT_AND",
      [TOK_BIT_OR] = "BIT_OR",
      [TOK_BIT_XOR] = "BIT_XOR",
      [TOK_BIT_SHL] = "BIT_SHL",
      [TOK_BIT_SHR] = "BIT_SHR",
      [TOK_BIT_NOT] = "BIT_NOT",
      [TOK_SAFE_ACCESS] = "SAFE_ACCESS",
      [TOK_EXIST] = "EXIST",
      [TOK_CAST] = "CAST",
      [TOK_PATTERN] = "PATTERN",
      [TOK_HASH] = "HASH",
      [TOK_MATMUL] = "MATMUL",
      [TOK_FMA] = "FMA",
      [TOK_LOCK] = "LOCK",
      [TOK_ATOMIC_BANG] = "ATOMIC_BANG",
      [TOK_PLUS_ASSIGN] = "PLUS_ASSIGN",
      [TOK_MINUS_ASSIGN] = "MINUS_ASSIGN",
      [TOK_STAR_ASSIGN] = "STAR_ASSIGN",
      [TOK_SLASH_ASSIGN] = "SLASH_ASSIGN",
      [TOK_LPAREN] = "LPAREN",
      [TOK_RPAREN] = "RPAREN",
      [TOK_LBRACKET] = "LBRACKET",
      [TOK_RBRACKET] = "RBRACKET",
      [TOK_LBRACE] = "LBRACE",
      [TOK_RBRACE] = "RBRACE",
      [TOK_COMMA] = "COMMA",
      [TOK_DOT] = "DOT",
      [TOK_DOTDOT] = "DOTDOT",
      [TOK_COLON] = "COLON",
      [TOK_SEMICOLON] = "SEMICOLON",
      [TOK_ARROW] = "ARROW",
      [TOK_LARROW] = "LARROW",
      [TOK_AT] = "AT",
      [TOK_NEWLINE] = "NEWLINE",
      [TOK_IMPORT] = "IMPORT",
      [TOK_FROM] = "FROM",
      [TOK_MODULE] = "MODULE",
      [TOK_EXPORT] = "EXPORT",
      [TOK_AS] = "AS",
      [TOK_INCLUDE] = "INCLUDE",
      [TOK_TYPE_KW] = "TYPE",
      [TOK_IN] = "IN",
      [TOK_TRUE] = "TRUE",
      [TOK_FALSE] = "FALSE",
      [TOK_NONE_LIT] = "NONE",
  };
  if (type >= 0 && type < TOK_COUNT && names[type])
    return names[type];
  return "???";
}
