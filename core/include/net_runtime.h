/*
 * net_runtime.h – Network Runtime for Vir Stdlib
 * ================================================
 * Phase 3 – G1
 */

#ifndef VIR_NET_RUNTIME_H
#define VIR_NET_RUNTIME_H

#ifdef __cplusplus
extern "C" {
#endif

int vir_net_init(void);

/* TCP */
int vir_net_tcp_connect(const char *host, int port);
int vir_net_tcp_listen(const char *bind_addr, int port);
int vir_net_tcp_accept(int server_slot);
int vir_net_send(int slot, const void *data, int len);
int vir_net_recv(int slot, void *buf, int maxlen);
int vir_net_close(int slot);

/* UDP */
int vir_net_udp_bind(const char *addr, int port);
int vir_net_udp_sendto(int slot, const void *data, int len,
                       const char *host, int port);
int vir_net_udp_recvfrom(int slot, void *buf, int maxlen,
                         char *from_addr, int addr_len, int *from_port);

/* DNS */
int vir_net_resolve(const char *hostname, char *out_addr, int out_len);

/* Utils */
int vir_net_set_nonblocking(int slot);
int vir_net_poll(int *slots, int nslots, int timeout_ms);

/* HTTP */
int vir_net_http_get(const char *host, int port, const char *path,
                     char *out_buf, int out_len);

#ifdef __cplusplus
}
#endif

#endif /* VIR_NET_RUNTIME_H */
