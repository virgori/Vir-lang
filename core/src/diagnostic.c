#include "diagnostic.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>

#define ANSI_RESET   "\033[0m"
#define ANSI_BOLD    "\033[1m"
#define ANSI_DIM     "\033[2m"
#define ANSI_RED     "\033[31m"
#define ANSI_YELLOW  "\033[33m"
#define ANSI_CYAN    "\033[36m"
#define ANSI_MAGENTA "\033[35m"
#define ANSI_WHITE   "\033[37m"
#define ANSI_BRED    "\033[1;31m"
#define ANSI_BYELLOW "\033[1;33m"
#define ANSI_BCYAN   "\033[1;36m"
#define ANSI_BWHITE  "\033[1;37m"

#define BOX_H    "\xe2\x94\x80"
#define BOX_V    "\xe2\x94\x82"
#define BOX_BULL "\xe2\x80\xa2"

static const char *severity_label[] = {
  "Fatal", "Error", "Warning", "Note", "Help", "Suggestion", "Debug", "Internal Compiler Error"
};

static const char *severity_color[] = {
  ANSI_BRED, ANSI_BRED, ANSI_BYELLOW, ANSI_DIM, ANSI_BCYAN, ANSI_BCYAN, ANSI_DIM, ANSI_MAGENTA
};

static const char *phase_label[] = {
  "Lexer", "Parser", "Semantic", "IR Lowering", "IR Optimizer",
  "RegAlloc", "CodeGen", "Linker", "Module Resolver", "Borrow Checker"
};

static const char *stage_label[] = {
  "Stage-0 C-Core", "Stage-1 Vir-Native"
};

/* ═══════════════════════════════════════════════════════
 * Built-in Sinks
 * ═══════════════════════════════════════════════════════ */

static size_t stderr_write(diag_sink_t *sink, const char *data, size_t len) {
  (void)sink;
  return fwrite(data, 1, len, stderr);
}

diag_sink_t diag_sink_stderr(void) {
  diag_sink_t s;
  s.write = stderr_write;
  s.userdata = NULL;
  return s;
}

typedef struct {
  char *buf;
  size_t cap;
  size_t used;
} buffer_sink_ctx;

static size_t buffer_write(diag_sink_t *sink, const char *data, size_t len) {
  buffer_sink_ctx *ctx = (buffer_sink_ctx*)sink->userdata;
  if (!ctx || ctx->used >= ctx->cap) return 0;
  size_t avail = ctx->cap - ctx->used;
  size_t to_write = len < avail ? len : avail;
  memcpy(ctx->buf + ctx->used, data, to_write);
  ctx->used += to_write;
  return to_write;
}

diag_sink_t diag_sink_buffer(char *buf, size_t capacity) {
  buffer_sink_ctx *ctx = malloc(sizeof(buffer_sink_ctx));
  ctx->buf = buf;
  ctx->cap = capacity;
  ctx->used = 0;
  diag_sink_t s;
  s.write = buffer_write;
  s.userdata = ctx;
  return s;
}

size_t diag_sink_buffer_used(const diag_sink_t *sink) {
  if (sink->write == buffer_write && sink->userdata) {
    return ((buffer_sink_ctx*)sink->userdata)->used;
  }
  return 0;
}

static void sink_print(diag_sink_t *sink, const char *fmt, ...) {
  char buf[1024];
  va_list args;
  va_start(args, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  if (n > 0) {
    sink->write(sink, buf, (size_t)n);
  }
}

/* ═══════════════════════════════════════════════════════
 * Context / Lifecycle
 * ═══════════════════════════════════════════════════════ */

void diag_init(diag_context_t *ctx, diag_stage_t stage, diag_format_t fmt) {
  memset(ctx, 0, sizeof(*ctx));
  ctx->active_stage = stage;
  ctx->format = fmt;
  ctx->sink = diag_sink_stderr();
  ctx->report_code = 0;
}

diag_file_id_t diag_register_source(diag_context_t *ctx, const char *filename, const char *text, size_t len) {
  if (ctx->file_count >= DIAG_MAX_FILES) return DIAG_NO_FILE;
  diag_file_id_t id = ctx->file_count++;
  ctx->files[id].filename = filename ? strdup(filename) : NULL;
  if (text) {
    char *copy = malloc(len + 1);
    if (copy) {
      memcpy(copy, text, len);
      copy[len] = '\0';
    }
    ctx->files[id].source = copy;
  } else {
    ctx->files[id].source = NULL;
  }
  ctx->files[id].source_len = len;
  ctx->files[id].active = 1;
  return id;
}

void diag_set_sink(diag_context_t *ctx, diag_sink_t sink) {
  ctx->sink = sink;
}

/* ═══════════════════════════════════════════════════════
 * Arena
 * ═══════════════════════════════════════════════════════ */

diag_str_t diag_intern_len(diag_context_t *ctx, const char *str, uint32_t len) {
  if (!str || len == 0) return DIAG_STR_EMPTY;
  if (ctx->arena.used + len > DIAG_ARENA_SIZE) {
    ctx->overflow = 1;
    return DIAG_STR_EMPTY;
  }
  uint32_t offset = ctx->arena.used;
  memcpy(ctx->arena.data + offset, str, len);
  ctx->arena.used += len;
  diag_str_t res = {offset, len};
  return res;
}

diag_str_t diag_intern(diag_context_t *ctx, const char *str) {
  if (!str) return DIAG_STR_EMPTY;
  return diag_intern_len(ctx, str, (uint32_t)strlen(str));
}

diag_str_t diag_intern_fmt(diag_context_t *ctx, const char *fmt, ...) {
  char buf[1024];
  va_list args;
  va_start(args, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  if (n <= 0) return DIAG_STR_EMPTY;
  return diag_intern_len(ctx, buf, (uint32_t)n);
}

const char *diag_str_ptr(const diag_context_t *ctx, diag_str_t s) {
  if (s.length == 0) return "";
  return ctx->arena.data + s.offset;
}

/* ═══════════════════════════════════════════════════════
 * Source Utilities
 * ═══════════════════════════════════════════════════════ */

const char *diag_get_line(const diag_context_t *ctx, diag_file_id_t file, uint32_t line, uint32_t *out_len) {
  if (file >= ctx->file_count || !ctx->files[file].active || line == 0) return NULL;
  const char *src = ctx->files[file].source;
  size_t len = ctx->files[file].source_len;
  uint32_t current_line = 1;
  const char *line_start = src;
  for (size_t i = 0; i <= len; i++) {
    if (i == len || src[i] == '\n') {
      if (current_line == line) {
        uint32_t l = (uint32_t)(src + i - line_start);
        if (l > 0 && line_start[l - 1] == '\r') l--;
        *out_len = l;
        return line_start;
      }
      current_line++;
      line_start = src + i + 1;
    }
  }
  return NULL;
}

int diag_offset_to_lc(const diag_context_t *ctx, diag_file_id_t file, uint32_t byte_offset, uint32_t *out_line, uint32_t *out_col) {
  if (file >= ctx->file_count || !ctx->files[file].active) return 0;
  const char *src = ctx->files[file].source;
  size_t len = ctx->files[file].source_len;
  if (byte_offset > len) byte_offset = (uint32_t)len;
  uint32_t line = 1, col = 1;
  for (uint32_t i = 0; i < byte_offset; i++) {
    if (src[i] == '\n') {
      line++;
      col = 1;
    } else {
      col++;
    }
  }
  *out_line = line;
  *out_col = col;
  return 1;
}

uint32_t diag_lc_to_offset(const diag_context_t *ctx, diag_file_id_t file, uint32_t line, uint32_t col) {
  if (file >= ctx->file_count || !ctx->files[file].active || line == 0 || col == 0) return 0xFFFFFFFFu;
  const char *src = ctx->files[file].source;
  size_t len = ctx->files[file].source_len;
  uint32_t current_line = 1, current_col = 1;
  for (uint32_t i = 0; i < len; i++) {
    if (current_line == line && current_col == col) return i;
    if (src[i] == '\n') {
      current_line++;
      current_col = 1;
    } else {
      current_col++;
    }
  }
  if (current_line == line && current_col == col) return (uint32_t)len;
  return 0xFFFFFFFFu;
}

/* ═══════════════════════════════════════════════════════
 * Span
 * ═══════════════════════════════════════════════════════ */

diag_span_t diag_span(diag_file_id_t file, uint32_t start_byte, uint32_t end_byte) {
  diag_span_t s;
  memset(&s, 0, sizeof(s));
  s.file_id = file;
  s.start_byte = start_byte;
  s.end_byte = end_byte;
  return s;
}

diag_span_t diag_span_lc(diag_file_id_t file, uint32_t line, uint32_t col, uint32_t length) {
  diag_span_t s;
  memset(&s, 0, sizeof(s));
  s.file_id = file;
  s.line = line;
  s.col = col;
  s.end_line = line;
  s.end_col = col + length;
  return s;
}

void diag_span_resolve(const diag_context_t *ctx, diag_span_t *span) {
  if (span->file_id == DIAG_NO_FILE) return;
  if (span->line == 0 && span->start_byte != span->end_byte) {
    diag_offset_to_lc(ctx, span->file_id, span->start_byte, &span->line, &span->col);
    diag_offset_to_lc(ctx, span->file_id, span->end_byte, &span->end_line, &span->end_col);
  }
}

/* ═══════════════════════════════════════════════════════
 * Emit
 * ═══════════════════════════════════════════════════════ */

diag_entry_t *diag_emit(diag_context_t *ctx, diag_severity_t severity, diag_category_t category,
                        diag_phase_t phase, uint32_t code, diag_span_t span, const char *summary) {
  if (ctx->count >= DIAG_MAX_ENTRIES) {
    ctx->overflow = 1;
    return NULL;
  }
  diag_entry_t *e = &ctx->entries[ctx->count++];
  memset(e, 0, sizeof(*e));
  e->severity = severity;
  e->category = category;
  e->phase = phase;
  e->stage = ctx->active_stage;
  e->code = code;
  e->span = span;
  e->summary = diag_intern(ctx, summary);

  if (severity == DIAG_FATAL) ctx->fatal_count++;
  else if (severity == DIAG_ERROR) ctx->error_count++;
  else if (severity == DIAG_WARNING) ctx->warning_count++;
  else if (severity == DIAG_NOTE) ctx->note_count++;

  return e;
}

diag_entry_t *diag_emit_lc(diag_context_t *ctx, diag_severity_t severity, diag_category_t category,
                           diag_phase_t phase, uint32_t code, diag_file_id_t file,
                           uint32_t line, uint32_t col, uint32_t length, const char *summary) {
  diag_span_t s = diag_span_lc(file, line, col, length);
  s.start_byte = diag_lc_to_offset(ctx, file, line, col);
  s.end_byte = s.start_byte + length; // rough approximation if length is bytes
  return diag_emit(ctx, severity, category, phase, code, s, summary);
}

void diag_add_label(diag_context_t *ctx, diag_entry_t *entry, diag_span_t span, diag_label_role_t role, const char *text) {
  if (!entry || entry->label_count >= DIAG_MAX_LABELS) return;
  diag_label_t *l = &entry->labels[entry->label_count++];
  l->span = span;
  l->role = role;
  l->text = diag_intern(ctx, text);
}

void diag_add_fix(diag_context_t *ctx, diag_entry_t *entry, const char *message, diag_span_t span, const char *replacement) {
  if (!entry || entry->fix_count >= DIAG_MAX_FIXES) return;
  diag_fix_t *f = &entry->fixes[entry->fix_count++];
  f->message = diag_intern(ctx, message);
  f->span = span;
  f->replacement = diag_intern(ctx, replacement);
  f->is_applicable = 1;
}

void diag_add_suggestion(diag_context_t *ctx, diag_entry_t *entry, const char *text) {
  if (!entry || entry->fix_count >= DIAG_MAX_FIXES) return;
  diag_fix_t *f = &entry->fixes[entry->fix_count++];
  f->message = diag_intern(ctx, text);
  f->is_applicable = 0;
}

void diag_set_detail(diag_context_t *ctx, diag_entry_t *entry, const char *detail) {
  if (entry) entry->detail = diag_intern(ctx, detail);
}

void diag_set_analysis(diag_context_t *ctx, diag_entry_t *entry,
                       const char *analysis) {
  entry->analysis = diag_intern(ctx, analysis);
}

void diag_add_cause(diag_context_t *ctx, diag_entry_t *entry,
                    const char *cause) {
  if (!entry) return; if (entry->cause_count < 8) {
    entry->causes[entry->cause_count++] = diag_intern(ctx, cause);
  }
}

void diag_add_action(diag_context_t *ctx, diag_entry_t *entry,
                     const char *action) {
  if (!entry) return; if (entry->action_count < 8) {
    entry->actions[entry->action_count++] = diag_intern(ctx, action);
  }
}

void diag_add_related_span(diag_context_t *ctx, diag_entry_t *entry,
                           diag_span_t span, const char *label) {
  if (entry->related_count < 8) {
    entry->related[entry->related_count] = span;
    entry->related_labels[entry->related_count] = diag_intern(ctx, label);
    entry->related_count++;
  }
}

void diag_set_recovery(diag_entry_t *entry, uint32_t token_index, uint32_t sync_token_index, uint32_t depth, int recovered) {
  if (entry) {
    entry->has_recovery = 1;
    entry->recovery.token_index = token_index;
    entry->recovery.sync_token_index = sync_token_index;
    entry->recovery.parser_depth = depth;
    entry->recovery.recovered = recovered;
  }
}

void diag_ice_set_state(diag_context_t *ctx, diag_entry_t *entry, const char *module, const char *pass,
                        int32_t ast_node_type, uint32_t token_index, uint32_t ir_opcode) {
  if (entry) {
    entry->has_ice = 1;
    entry->ice.current_module = diag_intern(ctx, module);
    entry->ice.compiler_pass = diag_intern(ctx, pass);
    entry->ice.ast_node_type = ast_node_type;
    entry->ice.token_index = token_index;
    entry->ice.ir_opcode = ir_opcode;
  }
}

/* ═══════════════════════════════════════════════════════
 * Rendering
 * ═══════════════════════════════════════════════════════ */

static void render_rule(diag_sink_t *sink, int use_color, int heavy) {
  if (use_color) sink_print(sink, "%s", ANSI_DIM);
  for (int i = 0; i < 47; i++) sink_print(sink, "%s", heavy ? "\xe2\x95\x90" : "\xe2\x94\x80"); // ═ or ─
  if (use_color) sink_print(sink, "%s", ANSI_RESET);
  sink_print(sink, "\n");
}

static void render_terminal(diag_context_t *ctx, const diag_entry_t *e) {
  diag_sink_t *s = &ctx->sink;
  int color = (ctx->format == DIAG_FMT_TERMINAL);

  diag_span_t span = e->span;
  diag_span_resolve(ctx, &span);

  const char *prefix = "E";
  const char *result_str = "FAILED";
  const char *result_color = ANSI_BRED;
  switch (e->severity) {
    case DIAG_WARNING: prefix = "W"; result_str = "WARNING"; result_color = ANSI_YELLOW; break;
    case DIAG_FATAL:   prefix = "F"; result_str = "FATAL"; result_color = ANSI_BRED; break;
    case DIAG_ICE:     prefix = "I"; result_str = "INTERNAL ERROR"; result_color = ANSI_MAGENTA; break;
    default: break;
  }

  sink_print(s, "\n");
  render_rule(s, color, 1);
  if (e->severity == DIAG_ICE) {
    if (color) sink_print(s, "%s%sINTERNAL COMPILER ERROR%s\n", result_color, ANSI_BOLD, ANSI_RESET);
    else sink_print(s, "INTERNAL COMPILER ERROR\n");
    render_rule(s, color, 1);
    sink_print(s, "\n");
    
    if (color) sink_print(s, "Code      : [%s%s%04u%s]\n", ANSI_BOLD, prefix, e->code, ANSI_RESET);
    else sink_print(s, "Code      : [%s%04u]\n", prefix, e->code);
    sink_print(s, "Subsystem : Compiler (%s)\n", phase_label[e->phase]);
    sink_print(s, "Version   : Vir 2.2.0\n");
    sink_print(s, "Stage     : %s\n", stage_label[e->stage]);
    
    sink_print(s, "\nDetails\n");
    render_rule(s, color, 0);
    sink_print(s, "%.*s\n", e->summary.length, diag_str_ptr(ctx, e->summary));
    if (e->analysis.length > 0) {
      sink_print(s, "%.*s\n", e->analysis.length, diag_str_ptr(ctx, e->analysis));
    }
    
    sink_print(s, "\nRecommendation\n");
    render_rule(s, color, 0);
    sink_print(s, "This indicates a compiler bug.\n\nPlease file an issue with:\n• source file\n• compiler version\n• reproduction steps\n• --dump-ast output\n");
    
    sink_print(s, "\n");
    render_rule(s, color, 1);
    return;
  }

  if (color) sink_print(s, "%sEXECUTION REPORT%s\n", ANSI_BOLD, ANSI_RESET);
  else sink_print(s, "EXECUTION REPORT\n");
  render_rule(s, color, 1);
  sink_print(s, "\n");

  /* Result */
  sink_print(s, "Result      : ");
  if (color) sink_print(s, "%s%s%s\n", result_color, result_str, ANSI_RESET);
  else sink_print(s, "%s\n", result_str);

  /* Code */
  if (color) {
    sink_print(s, "Code        : [%s%s%04u%s] %s%s%s\n", ANSI_BOLD, prefix, e->code, ANSI_RESET, ANSI_BOLD, phase_label[e->phase], ANSI_RESET);
  } else {
    sink_print(s, "Code        : [%s%04u] %s\n", prefix, e->code, phase_label[e->phase]);
  }
  
  sink_print(s, "Subsystem   : Compiler\n");
  sink_print(s, "Stage       : %s\n", stage_label[e->stage]);

  /* Location */
  sink_print(s, "\nLocation\n");
  render_rule(s, color, 0);
  if (span.file_id != DIAG_NO_FILE && span.file_id < ctx->file_count) {
    sink_print(s, "File        : %s\n", ctx->files[span.file_id].filename);
    sink_print(s, "Line        : %u\n", span.line);
  } else if (span.line > 0) {
    sink_print(s, "Line        : %u\n", span.line);
  }
  if (span.file_id != DIAG_NO_FILE) {
    uint32_t ll = 0;
    const char *ls = diag_get_line(ctx, span.file_id, span.line, &ll);
    if (ls) {
      sink_print(s, "\nSource\n");
      render_rule(s, color, 0);
      s->write(s, ls, ll);
      sink_print(s, "\n");
    }
  }
  if (e->related_count > 0) {
    sink_print(s, "\nRelated Locations\n");
    render_rule(s, color, 0);
    for (uint32_t i = 0; i < e->related_count; i++) {
      diag_span_t rspan = e->related[i];
      diag_span_resolve(ctx, &rspan);
      sink_print(s, "• %.*s", e->related_labels[i].length, diag_str_ptr(ctx, e->related_labels[i]));
      if (rspan.file_id != DIAG_NO_FILE && rspan.file_id < ctx->file_count) {
        sink_print(s, " (File: %s, Line: %u)\n", ctx->files[rspan.file_id].filename, rspan.line);
      } else if (rspan.line > 0) {
        sink_print(s, " (Line: %u)\n", rspan.line);
      } else {
        sink_print(s, "\n");
      }
      if (rspan.file_id != DIAG_NO_FILE) {
        uint32_t ll = 0;
        const char *ls = diag_get_line(ctx, rspan.file_id, rspan.line, &ll);
        if (ls) {
          sink_print(s, "  ");
          s->write(s, ls, ll);
          sink_print(s, "\n");
        }
      }
    }
  }

  /* Analysis */
  sink_print(s, "\nAnalysis\n");
  render_rule(s, color, 0);
  if (e->analysis.length > 0) {
    sink_print(s, "%.*s\n", e->analysis.length, diag_str_ptr(ctx, e->analysis));
  } else if (e->detail.length > 0) {
    sink_print(s, "%.*s\n", e->detail.length, diag_str_ptr(ctx, e->detail));
  } else {
    sink_print(s, "%.*s\n", e->summary.length, diag_str_ptr(ctx, e->summary));
  }

  /* Causes */
  if (e->cause_count > 0) {
    sink_print(s, "\nPossible Causes\n");
    render_rule(s, color, 0);
    for (uint32_t i = 0; i < e->cause_count; i++) {
      sink_print(s, "• %.*s\n", e->causes[i].length, diag_str_ptr(ctx, e->causes[i]));
    }
  }

  /* Action / Recommendation */
  if (e->action_count > 0 || e->fix_count > 0) {
    sink_print(s, "\nAction\n");
    render_rule(s, color, 0);
    for (uint32_t i = 0; i < e->action_count; i++) {
      sink_print(s, "• %.*s\n", e->actions[i].length, diag_str_ptr(ctx, e->actions[i]));
    }
    for (uint32_t i = 0; i < e->fix_count; i++) {
      const diag_fix_t *fix = &e->fixes[i];
      sink_print(s, "• %.*s\n", fix->message.length, diag_str_ptr(ctx, fix->message));
    }
  }

  sink_print(s, "\n");
  render_rule(s, color, 1);
}

static void render_plain(diag_context_t *ctx, const diag_entry_t *e) {
  diag_sink_t *s = &ctx->sink;
  const char *prefix = "E";
  if (e->severity == DIAG_WARNING) prefix = "W";
  
  diag_span_t span = e->span;
  diag_span_resolve(ctx, &span);

  const char *fname = span.file_id != DIAG_NO_FILE ? ctx->files[span.file_id].filename : "<unknown>";
  sink_print(s, "[%s] %s%04u %s:%u: %.*s\n",
             e->severity == DIAG_WARNING ? "WARN" : "FAIL",
             prefix, e->code,
             fname, span.line,
             e->summary.length, diag_str_ptr(ctx, e->summary));
}

void diag_render(diag_context_t *ctx, const diag_entry_t *entry) {
  if (ctx->format == DIAG_FMT_JSON) {
    diag_to_json(ctx, entry, &ctx->sink);
    sink_print(&ctx->sink, "\n");
  } else if (ctx->format == DIAG_FMT_PLAIN) {
    render_plain(ctx, entry);
  } else {
    render_terminal(ctx, entry);
  }
}

void diag_render_summary(diag_context_t *ctx) {
  // Handled directly in diag_render_all
  return;
}

void diag_render_all(diag_context_t *ctx) {
  if (ctx->format == DIAG_FMT_JSON) {
    diag_all_to_json(ctx, &ctx->sink);
    return;
  }

  diag_sink_t *s = &ctx->sink;
  int color = (ctx->format == DIAG_FMT_TERMINAL);

  // Filter mode
  if (ctx->report_code > 0) {
    int found = 0;
    for (uint32_t i = 0; i < ctx->count; i++) {
      if (ctx->entries[i].code == ctx->report_code) {
        diag_render(ctx, &ctx->entries[i]);
        found = 1;
      }
    }
    if (!found) {
      sink_print(s, "No execution report found for error code E%04u.\n", ctx->report_code);
    }
    return;
  }

  // If only 1 error, just render it fully
  if (ctx->count == 1) {
    diag_render(ctx, &ctx->entries[0]);
    return;
  }

  if (ctx->count == 0) return;

  // Render Summary Report
  sink_print(s, "\n");
  render_rule(s, color, 1);
  if (color) sink_print(s, "%sEXECUTION REPORT%s\n", ANSI_BOLD, ANSI_RESET);
  else sink_print(s, "EXECUTION REPORT\n");
  render_rule(s, color, 1);
  sink_print(s, "\nStatus : %sFAILED%s\n", color?ANSI_BRED:"", color?ANSI_RESET:"");
  sink_print(s, "Errors : %u\n", ctx->error_count + ctx->fatal_count);
  sink_print(s, "Warnings : %u\n\n", ctx->warning_count);

  // If 1-10 errors, compact table
  if (ctx->count <= 10) {
    for (uint32_t i = 0; i < ctx->count; i++) {
      diag_entry_t *e = &ctx->entries[i];
      diag_span_t span = e->span;
      diag_span_resolve(ctx, &span);

      const char *eprefix = "E";
      switch (e->severity) {
        case DIAG_WARNING: eprefix = "W"; break;
        case DIAG_FATAL: eprefix = "F"; break;
        case DIAG_ICE: eprefix = "I"; break;
        default: break;
      }
      
      if (color) {
        sink_print(s, "[%s%s%04u%s] %s%s%s\n", ANSI_BOLD, eprefix, e->code, ANSI_RESET, ANSI_BOLD, phase_label[e->phase], ANSI_RESET);
      } else {
        sink_print(s, "[%s%04u] %s\n", eprefix, e->code, phase_label[e->phase]);
      }
      
      if (span.file_id != DIAG_NO_FILE) {
        sink_print(s, "File : %s\nLine : %u\n", ctx->files[span.file_id].filename, span.line);
      } else if (span.line > 0) {
        sink_print(s, "Line : %u\n", span.line);
      }
      sink_print(s, "\n%.*s\n", e->summary.length, diag_str_ptr(ctx, e->summary));
      render_rule(s, color, 0);
    }
  } else {
    // > 10 errors, compact one-liners
    sink_print(s, "First errors:\n");
    render_rule(s, color, 0);
    uint32_t limit = ctx->count > 10 ? 10 : ctx->count;
    for (uint32_t i = 0; i < limit; i++) {
      diag_entry_t *e = &ctx->entries[i];
      diag_span_t span = e->span;
      diag_span_resolve(ctx, &span);
      const char *eprefix = "E";
      switch (e->severity) {
        case DIAG_WARNING: eprefix = "W"; break;
        case DIAG_FATAL: eprefix = "F"; break;
        case DIAG_ICE: eprefix = "I"; break;
        default: break;
      }
      if (color) {
        sink_print(s, "[%s%s%04u%s] ", ANSI_BOLD, eprefix, e->code, ANSI_RESET);
      } else {
        sink_print(s, "[%s%04u] ", eprefix, e->code);
      }
      
      if (span.file_id != DIAG_NO_FILE) {
        sink_print(s, "line %-4u ", span.line);
      } else if (span.line > 0) {
        sink_print(s, "line %-4u ", span.line);
      } else {
        sink_print(s, "          ");
      }
      sink_print(s, "%.*s\n", e->summary.length, diag_str_ptr(ctx, e->summary));
    }
    if (ctx->count > 10) {
      sink_print(s, "...\n(+%u more errors)\n", ctx->count - 10);
    }
  }

  sink_print(s, "\nRun:\n    vir build --report <ErrorCode>\nfor detailed diagnostics.\n");
}


/* ═══════════════════════════════════════════════════════
 * JSON Serializer
 * ═══════════════════════════════════════════════════════ */

static void json_escape_sink(diag_sink_t *s, const char *str, uint32_t len) {
  for (uint32_t i = 0; i < len; i++) {
    switch (str[i]) {
      case '"': sink_print(s, "\\\""); break;
      case '\\': sink_print(s, "\\\\"); break;
      case '\n': sink_print(s, "\\n"); break;
      case '\r': sink_print(s, "\\r"); break;
      case '\t': sink_print(s, "\\t"); break;
      default: {
        char c = str[i];
        s->write(s, &c, 1);
        break;
      }
    }
  }
}

size_t diag_to_json(diag_context_t *ctx, const diag_entry_t *entry, diag_sink_t *sink) {
  char temp_buf[4096];
  diag_sink_t mem_sink = diag_sink_buffer(temp_buf, sizeof(temp_buf));
  
  diag_span_t span = entry->span;
  diag_span_resolve(ctx, &span);

  sink_print(&mem_sink, "{");
  sink_print(&mem_sink, "\"schema_version\":%d,", DIAG_JSON_SCHEMA_VERSION);
  sink_print(&mem_sink, "\"severity\":\"%s\",", severity_label[entry->severity]);
  sink_print(&mem_sink, "\"code\":%u,", entry->code);
  sink_print(&mem_sink, "\"category\":%u,", entry->category);
  sink_print(&mem_sink, "\"phase\":\"%s\",", phase_label[entry->phase]);
  sink_print(&mem_sink, "\"stage\":\"%s\",", stage_label[entry->stage]);
  
  sink_print(&mem_sink, "\"summary\":\"");
  json_escape_sink(&mem_sink, diag_str_ptr(ctx, entry->summary), entry->summary.length);
  sink_print(&mem_sink, "\",");

  sink_print(&mem_sink, "\"detail\":\"");
  if (entry->detail.length > 0) json_escape_sink(&mem_sink, diag_str_ptr(ctx, entry->detail), entry->detail.length);
  sink_print(&mem_sink, "\",");

  sink_print(&mem_sink, "\"analysis\":\"");
  if (entry->analysis.length > 0) json_escape_sink(&mem_sink, diag_str_ptr(ctx, entry->analysis), entry->analysis.length);
  sink_print(&mem_sink, "\",");

  sink_print(&mem_sink, "\"causes\":[");
  for (uint32_t i = 0; i < entry->cause_count; i++) {
    sink_print(&mem_sink, "\"");
    json_escape_sink(&mem_sink, diag_str_ptr(ctx, entry->causes[i]), entry->causes[i].length);
    sink_print(&mem_sink, "\"");
    if (i < entry->cause_count - 1) sink_print(&mem_sink, ",");
  }
  sink_print(&mem_sink, "],");

  sink_print(&mem_sink, "\"actions\":[");
  for (uint32_t i = 0; i < entry->action_count; i++) {
    sink_print(&mem_sink, "\"");
    json_escape_sink(&mem_sink, diag_str_ptr(ctx, entry->actions[i]), entry->actions[i].length);
    sink_print(&mem_sink, "\"");
    if (i < entry->action_count - 1) sink_print(&mem_sink, ",");
  }
  sink_print(&mem_sink, "],");

  sink_print(&mem_sink, "\"primary_span\":{");
  if (span.file_id != DIAG_NO_FILE) {
    sink_print(&mem_sink, "\"file\":\"%s\",", ctx->files[span.file_id].filename);
  } else {
    sink_print(&mem_sink, "\"file\":\"\",");
  }
  sink_print(&mem_sink, "\"start_line\":%u,\"start_col\":%u,", span.line, span.col);
  sink_print(&mem_sink, "\"end_line\":%u,\"end_col\":%u", span.end_line, span.end_col);
  sink_print(&mem_sink, "},");

  sink_print(&mem_sink, "\"fixes\":[");
  for (uint32_t i = 0; i < entry->fix_count; i++) {
    const diag_fix_t *f = &entry->fixes[i];
    sink_print(&mem_sink, "{");
    sink_print(&mem_sink, "\"message\":\"");
    json_escape_sink(&mem_sink, diag_str_ptr(ctx, f->message), f->message.length);
    sink_print(&mem_sink, "\",\"replacement\":\"");
    if (f->replacement.length > 0) json_escape_sink(&mem_sink, diag_str_ptr(ctx, f->replacement), f->replacement.length);
    sink_print(&mem_sink, "\"}");
    if (i < entry->fix_count - 1) sink_print(&mem_sink, ",");
  }
  sink_print(&mem_sink, "]");

  if (entry->has_recovery) {
    sink_print(&mem_sink, ",\"recovery\":{\"token_index\":%u,\"sync_token_index\":%u,\"recovered\":%d}",
               entry->recovery.token_index, entry->recovery.sync_token_index, entry->recovery.recovered);
  }

  if (entry->has_ice) {
    sink_print(&mem_sink, ",\"ice\":{\"file\":\"%s\",\"line\":%u,\"func\":\"%s\"}",
               entry->ice.c_file, entry->ice.c_line, entry->ice.c_func);
  }

  sink_print(&mem_sink, "}");

  size_t written = diag_sink_buffer_used(&mem_sink);
  if (written > 0) {
    sink->write(sink, temp_buf, written);
  }
  return written;
}

size_t diag_all_to_json(diag_context_t *ctx, diag_sink_t *sink) {
  sink_print(sink, "[\n");
  for (uint32_t i = 0; i < ctx->count; i++) {
    diag_to_json(ctx, &ctx->entries[i], sink);
    if (i < ctx->count - 1) sink_print(sink, ",\n");
  }
  sink_print(sink, "\n]\n");
  return 0; // return dummy size
}

/* ═══════════════════════════════════════════════════════
 * Query
 * ═══════════════════════════════════════════════════════ */

int diag_has_errors(const diag_context_t *ctx) {
  return ctx->error_count > 0 || ctx->fatal_count > 0;
}

int diag_has_fatal(const diag_context_t *ctx) {
  return ctx->fatal_count > 0;
}

uint32_t diag_count(const diag_context_t *ctx, diag_severity_t severity) {
  uint32_t c = 0;
  for (uint32_t i = 0; i < ctx->count; i++) {
    if (ctx->entries[i].severity == severity) c++;
  }
  return c;
}

/* ═══════════════════════════════════════════════════════
 * Typo Recovery
 * ═══════════════════════════════════════════════════════ */

int diag_levenshtein(const char *a, const char *b, int max_dist) {
  int la = (int)strlen(a);
  int lb = (int)strlen(b);
  if (abs(la - lb) > max_dist) return max_dist + 1;
  int prev[128], curr[128];
  if (lb >= 127) return max_dist + 1;
  for (int j = 0; j <= lb; j++) prev[j] = j;
  for (int i = 1; i <= la; i++) {
    curr[0] = i;
    int row_min = curr[0];
    for (int j = 1; j <= lb; j++) {
      int cost = (a[i-1] == b[j-1]) ? 0 : 1;
      int del = prev[j] + 1;
      int ins = curr[j-1] + 1;
      int sub = prev[j-1] + cost;
      curr[j] = del < ins ? (del < sub ? del : sub) : (ins < sub ? ins : sub);
      if (curr[j] < row_min) row_min = curr[j];
    }
    if (row_min > max_dist) return max_dist + 1;
    memcpy(prev, curr, (size_t)(lb + 1) * sizeof(int));
  }
  return prev[lb];
}

const char *diag_suggest_typo(const char *input, const char *const *candidates, int count, int threshold) {
  const char *best = NULL;
  int best_dist = threshold + 1;
  for (int i = 0; i < count; i++) {
    int d = diag_levenshtein(input, candidates[i], threshold);
    if (d < best_dist) {
      best_dist = d;
      best = candidates[i];
    }
  }
  return best;
}

const char *diag_suggest_expected(diag_context_t *ctx, const diag_expect_ctx_t *ectx) {
  (void)ctx;
  (void)ectx;
  return NULL; // Stub
}
int g_diag_initialized = 0;
diag_context_t g_parser_diag = {0};
