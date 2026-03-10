/*
 * signer.c – Standalone HMAC-SHA256 Code Signer
 * ═══════════════════════════════════════════════
 * Spec §4.2 – Security Layer.
 *
 * Zero-dependency SHA-256 + HMAC-SHA256 implementation.
 * Signs and verifies all patched code with the Quizz-Core Key.
 */

#include "signer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#pragma comment(lib, "bcrypt.lib")
#endif

/* ═══════════════════════════════════════════════════════
 * Platform Random Bytes
 * ═══════════════════════════════════════════════════════ */

int vir_random_bytes(void *buf, size_t len)
{
#if defined(__APPLE__) || defined(__linux__)
    FILE *f = fopen("/dev/urandom", "rb");
    if (!f) return -1;
    size_t rd = fread(buf, 1, len, f);
    fclose(f);
    return (rd == len) ? 0 : -1;
#elif defined(_WIN32)
    /* Use BCryptGenRandom (Windows Vista+) */
    NTSTATUS status = BCryptGenRandom(NULL, (PUCHAR)buf, (ULONG)len,
                                      BCRYPT_USE_SYSTEM_PREFERRED_RNG);
    return (status == 0) ? 0 : -1;
#else
    /* Unknown platform – no cryptographic RNG available */
    (void)buf; (void)len;
    return -1;
#endif
}

/* ═══════════════════════════════════════════════════════
 * Hex Encoding
 * ═══════════════════════════════════════════════════════ */

void vir_hex_encode(const uint8_t *data, size_t len,
                    char *out, size_t out_size)
{
    static const char hex[] = "0123456789abcdef";
    size_t pos = 0;
    for (size_t i = 0; i < len && pos + 2 < out_size; i++) {
        out[pos++] = hex[(data[i] >> 4) & 0xF];
        out[pos++] = hex[data[i] & 0xF];
    }
    if (pos < out_size) out[pos] = '\0';
}

/* ═══════════════════════════════════════════════════════
 * SHA-256 Implementation (FIPS 180-4)
 * ═══════════════════════════════════════════════════════ */

static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define ROTR(x, n)   (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x, y, z)  (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)        (ROTR(x,  2) ^ ROTR(x, 13) ^ ROTR(x, 22))
#define EP1(x)        (ROTR(x,  6) ^ ROTR(x, 11) ^ ROTR(x, 25))
#define SIG0(x)       (ROTR(x,  7) ^ ROTR(x, 18) ^ ((x) >> 3))
#define SIG1(x)       (ROTR(x, 17) ^ ROTR(x, 19) ^ ((x) >> 10))

void sha256_init(sha256_ctx_t *ctx)
{
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
    ctx->count = 0;
}

static void sha256_transform(sha256_ctx_t *ctx, const uint8_t block[64])
{
    uint32_t W[64];
    uint32_t a, b, c, d, e, f, g, h;
    uint32_t t1, t2;

    for (int i = 0; i < 16; i++) {
        W[i] = ((uint32_t)block[i*4]     << 24)
             | ((uint32_t)block[i*4 + 1] << 16)
             | ((uint32_t)block[i*4 + 2] <<  8)
             | ((uint32_t)block[i*4 + 3]);
    }
    for (int i = 16; i < 64; i++) {
        W[i] = SIG1(W[i-2]) + W[i-7] + SIG0(W[i-15]) + W[i-16];
    }

    a = ctx->state[0]; b = ctx->state[1];
    c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5];
    g = ctx->state[6]; h = ctx->state[7];

    for (int i = 0; i < 64; i++) {
        t1 = h + EP1(e) + CH(e, f, g) + K[i] + W[i];
        t2 = EP0(a) + MAJ(a, b, c);
        h = g; g = f; f = e;
        e = d + t1;
        d = c; c = b; b = a;
        a = t1 + t2;
    }

    ctx->state[0] += a; ctx->state[1] += b;
    ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f;
    ctx->state[6] += g; ctx->state[7] += h;
}

void sha256_update(sha256_ctx_t *ctx, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    size_t buf_used = (size_t)(ctx->count % SHA256_BLOCK_SIZE);

    ctx->count += (uint64_t)len;

    while (len > 0) {
        size_t space = SHA256_BLOCK_SIZE - buf_used;
        size_t copy  = (len < space) ? len : space;
        memcpy(ctx->buffer + buf_used, p, copy);
        buf_used += copy;
        p   += copy;
        len -= copy;

        if (buf_used == SHA256_BLOCK_SIZE) {
            sha256_transform(ctx, ctx->buffer);
            buf_used = 0;
        }
    }
}

void sha256_final(sha256_ctx_t *ctx, uint8_t digest[SHA256_DIGEST_SIZE])
{
    uint64_t bitcount = ctx->count * 8;
    size_t buf_used = (size_t)(ctx->count % SHA256_BLOCK_SIZE);

    /* Padding */
    ctx->buffer[buf_used++] = 0x80;

    if (buf_used > 56) {
        memset(ctx->buffer + buf_used, 0, SHA256_BLOCK_SIZE - buf_used);
        sha256_transform(ctx, ctx->buffer);
        buf_used = 0;
    }
    memset(ctx->buffer + buf_used, 0, 56 - buf_used);

    /* Append length in bits (big-endian) */
    for (int i = 0; i < 8; i++) {
        ctx->buffer[56 + i] = (uint8_t)(bitcount >> (56 - i * 8));
    }
    sha256_transform(ctx, ctx->buffer);

    /* Output digest (big-endian) */
    for (int i = 0; i < 8; i++) {
        digest[i*4]     = (uint8_t)(ctx->state[i] >> 24);
        digest[i*4 + 1] = (uint8_t)(ctx->state[i] >> 16);
        digest[i*4 + 2] = (uint8_t)(ctx->state[i] >> 8);
        digest[i*4 + 3] = (uint8_t)(ctx->state[i]);
    }
}

void sha256_hash(const void *data, size_t len, uint8_t digest[SHA256_DIGEST_SIZE])
{
    sha256_ctx_t ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, digest);
}

/* ═══════════════════════════════════════════════════════
 * HMAC-SHA256 (RFC 2104)
 * ═══════════════════════════════════════════════════════ */

void hmac_sha256(const uint8_t *key, size_t key_len,
                 const void *data, size_t data_len,
                 uint8_t digest[SHA256_DIGEST_SIZE])
{
    uint8_t k_pad[SHA256_BLOCK_SIZE];
    uint8_t o_pad[SHA256_BLOCK_SIZE];
    uint8_t i_pad[SHA256_BLOCK_SIZE];
    sha256_ctx_t ctx;

    /* If key > block size, hash it first */
    uint8_t key_hash[SHA256_DIGEST_SIZE];
    if (key_len > SHA256_BLOCK_SIZE) {
        sha256_hash(key, key_len, key_hash);
        key     = key_hash;
        key_len = SHA256_DIGEST_SIZE;
    }

    memset(k_pad, 0, SHA256_BLOCK_SIZE);
    memcpy(k_pad, key, key_len);

    for (int i = 0; i < SHA256_BLOCK_SIZE; i++) i_pad[i] = k_pad[i] ^ 0x36;
    for (int i = 0; i < SHA256_BLOCK_SIZE; i++) o_pad[i] = k_pad[i] ^ 0x5C;

    /* Inner hash */
    uint8_t inner_hash[SHA256_DIGEST_SIZE];
    sha256_init(&ctx);
    sha256_update(&ctx, i_pad, SHA256_BLOCK_SIZE);
    sha256_update(&ctx, data, data_len);
    sha256_final(&ctx, inner_hash);

    /* Outer hash */
    sha256_init(&ctx);
    sha256_update(&ctx, o_pad, SHA256_BLOCK_SIZE);
    sha256_update(&ctx, inner_hash, SHA256_DIGEST_SIZE);
    sha256_final(&ctx, digest);

    /* Scrub sensitive data */
    memset(k_pad, 0, SHA256_BLOCK_SIZE);
    memset(i_pad, 0, SHA256_BLOCK_SIZE);
    memset(o_pad, 0, SHA256_BLOCK_SIZE);
    memset(inner_hash, 0, SHA256_DIGEST_SIZE);
}

/* ═══════════════════════════════════════════════════════
 * Signer API
 * ═══════════════════════════════════════════════════════ */

static uint8_t default_key[HMAC_KEY_SIZE] = {
    0x51, 0x75, 0x69, 0x7A, 0x7A, 0x2D, 0x43, 0x6F,  /* "Quizz-Co" */
    0x72, 0x65, 0x2D, 0x4B, 0x65, 0x79, 0x2D, 0x56,  /* "re-Key-V" */
    0x69, 0x72, 0x2D, 0x45, 0x6E, 0x67, 0x69, 0x6E,  /* "ir-Engin" */
    0x65, 0x2D, 0x76, 0x31, 0x2E, 0x30, 0x00, 0x00    /* "e-v1.0\0\0" */
};

int signer_init(signer_t *s, const uint8_t *key)
{
    memset(s, 0, sizeof(*s));
    if (key) {
        memcpy(s->key, key, HMAC_KEY_SIZE);
    } else {
        /* Use default key, or generate random */
        if (vir_random_bytes(s->key, HMAC_KEY_SIZE) != 0) {
            memcpy(s->key, default_key, HMAC_KEY_SIZE);
        }
    }
    s->sig_count = 0;
    return 0;
}

int signer_sign(signer_t *s, uint32_t patch_id,
                const void *code, size_t code_len)
{
    if (s->sig_count >= SIGNER_MAX_SIGS) return -1;

    code_signature_t *sig = &s->signatures[s->sig_count];
    memset(sig, 0, sizeof(*sig));
    sig->patch_id = patch_id;

    /* Generate nonce */
    vir_random_bytes(sig->nonce, sizeof(sig->nonce));

    /* Hash the code */
    sha256_hash(code, code_len, sig->code_hash);

    /* HMAC-SHA256(key, code_hash || nonce) */
    uint8_t combined[SHA256_DIGEST_SIZE + 16];
    memcpy(combined, sig->code_hash, SHA256_DIGEST_SIZE);
    memcpy(combined + SHA256_DIGEST_SIZE, sig->nonce, 16);
    hmac_sha256(s->key, HMAC_KEY_SIZE, combined, sizeof(combined), sig->hmac_sig);

    sig->valid = 1;
    s->sig_count++;
    return 0;
}

int signer_verify(const signer_t *s, uint32_t patch_id,
                  const void *code, size_t code_len)
{
    /* Find signature for this patch_id */
    const code_signature_t *sig = NULL;
    for (uint32_t i = 0; i < s->sig_count; i++) {
        if (s->signatures[i].patch_id == patch_id && s->signatures[i].valid) {
            sig = &s->signatures[i];
            break;
        }
    }
    if (!sig) return -1;  /* no signature found */

    /* Recompute code hash */
    uint8_t code_hash[SHA256_DIGEST_SIZE];
    sha256_hash(code, code_len, code_hash);

    /* Check code hash matches */
    uint8_t diff = 0;
    for (int i = 0; i < SHA256_DIGEST_SIZE; i++) {
        diff |= code_hash[i] ^ sig->code_hash[i];
    }
    if (diff != 0) return -1;  /* code was tampered */

    /* Recompute HMAC */
    uint8_t combined[SHA256_DIGEST_SIZE + 16];
    memcpy(combined, sig->code_hash, SHA256_DIGEST_SIZE);
    memcpy(combined + SHA256_DIGEST_SIZE, sig->nonce, 16);
    uint8_t computed_hmac[SHA256_DIGEST_SIZE];
    hmac_sha256(s->key, HMAC_KEY_SIZE, combined, sizeof(combined), computed_hmac);

    /* Constant-time HMAC comparison */
    diff = 0;
    for (int i = 0; i < SHA256_DIGEST_SIZE; i++) {
        diff |= computed_hmac[i] ^ sig->hmac_sig[i];
    }

    memset(computed_hmac, 0, SHA256_DIGEST_SIZE);
    return (diff == 0) ? 0 : -1;
}

int signer_revoke(signer_t *s, uint32_t patch_id)
{
    for (uint32_t i = 0; i < s->sig_count; i++) {
        if (s->signatures[i].patch_id == patch_id) {
            s->signatures[i].valid = 0;
            memset(s->signatures[i].hmac_sig, 0, SHA256_DIGEST_SIZE);
            return 0;
        }
    }
    return -1;
}

void signer_key_fingerprint(const signer_t *s, char *out, size_t out_size)
{
    uint8_t fp[SHA256_DIGEST_SIZE];
    sha256_hash(s->key, HMAC_KEY_SIZE, fp);
    vir_hex_encode(fp, 8, out, out_size);  /* first 8 bytes = 16 hex chars */
}
