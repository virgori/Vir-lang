/*
 * net_runtime.c – Network Runtime for Vir Stdlib
 * ================================================
 * Phase 3 – G1: Native backing for stdlib/vir/net/ and stdlib/vir/http/
 *
 * Provides: TCP/UDP sockets, DNS resolution, HTTP client basics.
 * Platform: macOS/Linux (POSIX sockets).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <fcntl.h>
#include <poll.h>

/* ═══════════════════════════════════════════════════════
 * Constants
 * ═══════════════════════════════════════════════════════ */

#define VIR_NET_MAX_CONNS      256
#define VIR_NET_RECV_BUF_SIZE  8192
#define VIR_NET_BACKLOG        128

/* ═══════════════════════════════════════════════════════
 * Types
 * ═══════════════════════════════════════════════════════ */

typedef enum {
    VIR_SOCK_TCP = 0,
    VIR_SOCK_UDP = 1,
} vir_sock_type_t;

typedef struct {
    int              fd;
    vir_sock_type_t  type;
    int              connected;
    int              listening;
    char             remote_addr[64];
    int              remote_port;
} vir_socket_t;

typedef struct {
    vir_socket_t    sockets[VIR_NET_MAX_CONNS];
    int             count;
} vir_net_ctx_t;

static vir_net_ctx_t g_net;

/* ═══════════════════════════════════════════════════════
 * Socket Management
 * ═══════════════════════════════════════════════════════ */

static int alloc_slot(void) {
    for (int i = 0; i < VIR_NET_MAX_CONNS; i++) {
        if (g_net.sockets[i].fd <= 0) return i;
    }
    return -1;
}

int vir_net_init(void) {
    memset(&g_net, 0, sizeof(g_net));
    return 0;
}

int vir_net_tcp_connect(const char *host, int port) {
    int slot = alloc_slot();
    if (slot < 0) return -1;

    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    char port_str[8];
    snprintf(port_str, sizeof(port_str), "%d", port);

    if (getaddrinfo(host, port_str, &hints, &res) != 0) return -1;

    int fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (fd < 0) { freeaddrinfo(res); return -1; }

    if (connect(fd, res->ai_addr, res->ai_addrlen) < 0) {
        close(fd);
        freeaddrinfo(res);
        return -1;
    }
    freeaddrinfo(res);

    g_net.sockets[slot].fd        = fd;
    g_net.sockets[slot].type      = VIR_SOCK_TCP;
    g_net.sockets[slot].connected = 1;
    g_net.sockets[slot].remote_port = port;
    snprintf(g_net.sockets[slot].remote_addr,
             sizeof(g_net.sockets[slot].remote_addr), "%s", host);
    g_net.count++;
    return slot;
}

int vir_net_tcp_listen(const char *bind_addr, int port) {
    int slot = alloc_slot();
    if (slot < 0) return -1;

    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;

    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(port);
    addr.sin_addr.s_addr = bind_addr ? inet_addr(bind_addr) : INADDR_ANY;

    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }
    if (listen(fd, VIR_NET_BACKLOG) < 0) {
        close(fd);
        return -1;
    }

    g_net.sockets[slot].fd        = fd;
    g_net.sockets[slot].type      = VIR_SOCK_TCP;
    g_net.sockets[slot].listening = 1;
    g_net.count++;
    return slot;
}

int vir_net_tcp_accept(int server_slot) {
    if (server_slot < 0 || server_slot >= VIR_NET_MAX_CONNS) return -1;
    vir_socket_t *srv = &g_net.sockets[server_slot];
    if (!srv->listening) return -1;

    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);
    int client_fd = accept(srv->fd, (struct sockaddr *)&client_addr, &addr_len);
    if (client_fd < 0) return -1;

    int slot = alloc_slot();
    if (slot < 0) { close(client_fd); return -1; }

    g_net.sockets[slot].fd        = client_fd;
    g_net.sockets[slot].type      = VIR_SOCK_TCP;
    g_net.sockets[slot].connected = 1;
    g_net.sockets[slot].remote_port = ntohs(client_addr.sin_port);
    inet_ntop(AF_INET, &client_addr.sin_addr,
              g_net.sockets[slot].remote_addr,
              sizeof(g_net.sockets[slot].remote_addr));
    g_net.count++;
    return slot;
}

int vir_net_send(int slot, const void *data, int len) {
    if (slot < 0 || slot >= VIR_NET_MAX_CONNS) return -1;
    vir_socket_t *s = &g_net.sockets[slot];
    if (s->fd <= 0 || !s->connected) return -1;
    return (int)send(s->fd, data, len, 0);
}

int vir_net_recv(int slot, void *buf, int maxlen) {
    if (slot < 0 || slot >= VIR_NET_MAX_CONNS) return -1;
    vir_socket_t *s = &g_net.sockets[slot];
    if (s->fd <= 0 || !s->connected) return -1;
    return (int)recv(s->fd, buf, maxlen, 0);
}

int vir_net_close(int slot) {
    if (slot < 0 || slot >= VIR_NET_MAX_CONNS) return -1;
    vir_socket_t *s = &g_net.sockets[slot];
    if (s->fd > 0) {
        close(s->fd);
        s->fd = 0;
        s->connected = 0;
        s->listening = 0;
        g_net.count--;
    }
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * UDP
 * ═══════════════════════════════════════════════════════ */

int vir_net_udp_bind(const char *addr, int port) {
    int slot = alloc_slot();
    if (slot < 0) return -1;

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return -1;

    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family      = AF_INET;
    sa.sin_port        = htons(port);
    sa.sin_addr.s_addr = addr ? inet_addr(addr) : INADDR_ANY;

    if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
        close(fd);
        return -1;
    }

    g_net.sockets[slot].fd   = fd;
    g_net.sockets[slot].type = VIR_SOCK_UDP;
    g_net.count++;
    return slot;
}

int vir_net_udp_sendto(int slot, const void *data, int len,
                       const char *host, int port) {
    if (slot < 0 || slot >= VIR_NET_MAX_CONNS) return -1;
    vir_socket_t *s = &g_net.sockets[slot];
    if (s->fd <= 0) return -1;

    struct sockaddr_in dest;
    memset(&dest, 0, sizeof(dest));
    dest.sin_family      = AF_INET;
    dest.sin_port        = htons(port);
    dest.sin_addr.s_addr = inet_addr(host);

    return (int)sendto(s->fd, data, len, 0,
                       (struct sockaddr *)&dest, sizeof(dest));
}

int vir_net_udp_recvfrom(int slot, void *buf, int maxlen,
                         char *from_addr, int addr_len, int *from_port) {
    if (slot < 0 || slot >= VIR_NET_MAX_CONNS) return -1;
    vir_socket_t *s = &g_net.sockets[slot];
    if (s->fd <= 0) return -1;

    struct sockaddr_in src;
    socklen_t slen = sizeof(src);
    int n = (int)recvfrom(s->fd, buf, maxlen, 0,
                          (struct sockaddr *)&src, &slen);
    if (n > 0) {
        if (from_addr && addr_len > 0) {
            inet_ntop(AF_INET, &src.sin_addr, from_addr, addr_len);
        }
        if (from_port) *from_port = ntohs(src.sin_port);
    }
    return n;
}

/* ═══════════════════════════════════════════════════════
 * DNS Resolution
 * ═══════════════════════════════════════════════════════ */

int vir_net_resolve(const char *hostname, char *out_addr, int out_len) {
    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;

    if (getaddrinfo(hostname, NULL, &hints, &res) != 0) return -1;

    struct sockaddr_in *addr = (struct sockaddr_in *)res->ai_addr;
    inet_ntop(AF_INET, &addr->sin_addr, out_addr, out_len);
    freeaddrinfo(res);
    return 0;
}

/* ═══════════════════════════════════════════════════════
 * Non-blocking & Poll
 * ═══════════════════════════════════════════════════════ */

int vir_net_set_nonblocking(int slot) {
    if (slot < 0 || slot >= VIR_NET_MAX_CONNS) return -1;
    int fd = g_net.sockets[slot].fd;
    if (fd <= 0) return -1;
    int flags = fcntl(fd, F_GETFL, 0);
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

int vir_net_poll(int *slots, int nslots, int timeout_ms) {
    if (nslots <= 0 || nslots > VIR_NET_MAX_CONNS) return -1;

    struct pollfd fds[VIR_NET_MAX_CONNS];
    for (int i = 0; i < nslots; i++) {
        int sl = slots[i];
        fds[i].fd     = (sl >= 0 && sl < VIR_NET_MAX_CONNS) ?
                         g_net.sockets[sl].fd : -1;
        fds[i].events = POLLIN;
        fds[i].revents = 0;
    }
    return poll(fds, nslots, timeout_ms);
}

/* ═══════════════════════════════════════════════════════
 * HTTP Client (minimal GET)
 * ═══════════════════════════════════════════════════════ */

int vir_net_http_get(const char *host, int port, const char *path,
                     char *out_buf, int out_len) {
    int sl = vir_net_tcp_connect(host, port);
    if (sl < 0) return -1;

    /* Build HTTP/1.1 GET request */
    char req[512];
    int req_len = snprintf(req, sizeof(req),
        "GET %s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n",
        path, host);

    if (vir_net_send(sl, req, req_len) < 0) {
        vir_net_close(sl);
        return -1;
    }

    /* Read response */
    int total = 0;
    while (total < out_len - 1) {
        int n = vir_net_recv(sl, out_buf + total, out_len - 1 - total);
        if (n <= 0) break;
        total += n;
    }
    out_buf[total] = '\0';
    vir_net_close(sl);
    return total;
}
