/*
 * signer.h – Internal Code Signer (HMAC-SHA256)
 * ===============================================
 * Spec §4.2 – Mọi đoạn mã được vá phải đi kèm mã băm
 * được ký bởi Quizz-Core Key.
 */

#ifndef VIR_SIGNER_H
#define VIR_SIGNER_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════
 * SHA-256 (Lightweight, standalone implementation)
 * ═══════════════════════════════════════════════════════ */

#define SHA256_DIGEST_SIZE 32
#define SHA256_BLOCK_SIZE  64

typedef struct {
    uint32_t state[8];
    uint64_t count;
    uint8_t  buffer[SHA256_BLOCK_SIZE];
} sha256_ctx_t;

void sha256_init(sha256_ctx_t *ctx);
void sha256_update(sha256_ctx_t *ctx, const void *data, size_t len);
void sha256_final(sha256_ctx_t *ctx, uint8_t digest[SHA256_DIGEST_SIZE]);
void sha256_hash(const void *data, size_t len, uint8_t digest[SHA256_DIGEST_SIZE]);

/* ═══════════════════════════════════════════════════════
 * HMAC-SHA256
 * ═══════════════════════════════════════════════════════ */

#define HMAC_KEY_SIZE 32

void hmac_sha256(const uint8_t *key, size_t key_len,
                 const void *data, size_t data_len,
                 uint8_t digest[SHA256_DIGEST_SIZE]);

/* ═══════════════════════════════════════════════════════
 * Code Signature
 * ═══════════════════════════════════════════════════════ */

typedef struct {
    uint32_t patch_id;
    uint8_t  code_hash[SHA256_DIGEST_SIZE];
    uint8_t  hmac_sig[SHA256_DIGEST_SIZE];
    uint8_t  nonce[16];
    int      valid;
} code_signature_t;

/* ═══════════════════════════════════════════════════════
 * Signer
 * ═══════════════════════════════════════════════════════ */

#define SIGNER_MAX_SIGS 256

typedef struct {
    uint8_t          key[HMAC_KEY_SIZE];
    code_signature_t signatures[SIGNER_MAX_SIGS];
    uint32_t         sig_count;
} signer_t;

/* ── API ─────────────────────────────────────────────── */

int  signer_init(signer_t *s, const uint8_t *key);  /* NULL key → random */
int  signer_sign(signer_t *s, uint32_t patch_id,
                 const void *code, size_t code_len);
int  signer_verify(const signer_t *s, uint32_t patch_id,
                   const void *code, size_t code_len);
int  signer_revoke(signer_t *s, uint32_t patch_id);
void signer_key_fingerprint(const signer_t *s,
                            char *out, size_t out_size);

/* Random bytes (platform-agnostic) */
int vir_random_bytes(void *buf, size_t len);

/* Hex conversion */
void vir_hex_encode(const uint8_t *data, size_t len,
                    char *out, size_t out_size);

#ifdef __cplusplus
}
#endif

#endif /* VIR_SIGNER_H */
