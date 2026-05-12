/*
 * bridge_native.c – Native C Backing for Vir Stdlib extern Functions
 * ====================================================================
 * Provides platform-specific implementations for IoT, TLS, and OS
 * functions that stdlib .vri files declare as `extern func native_*`.
 *
 * IoT functions require platform-specific hardware access:
 *   - Linux:  /dev/gpiochip*, /dev/i2c-*, /dev/spidev*, /dev/ttyUSB*
 *   - macOS:  Stubs only (no GPIO/I2C/SPI hardware)
 *
 * TLS uses OS-native crypto:
 *   - macOS:  Security.framework (SecureTransport)
 *   - Linux:  OpenSSL (if available)
 *
 * OS functions use POSIX APIs directly.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <signal.h>

/* ═══════════════════════════════════════════════════════
 * §1  OS / Process Functions
 * ═══════════════════════════════════════════════════════ */

int native_pipe(int pipefd[2]) {
    return pipe(pipefd);
}

int native_mkfifo(const char *pathname, int mode) {
    return mkfifo(pathname, (mode_t)mode);
}

int native_dup2(int oldfd, int newfd) {
    return dup2(oldfd, newfd);
}

int native_kill(int pid, int sig) {
    return kill((pid_t)pid, sig);
}

int native_signal_action(int signum, void (*handler)(int)) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = handler;
    sigemptyset(&sa.sa_mask);
    return sigaction(signum, &sa, NULL);
}

/* ═══════════════════════════════════════════════════════
 * §2  IoT – GPIO (Linux /dev/gpiochip* via ioctl)
 * ═══════════════════════════════════════════════════════ */

#if defined(__linux__)

#include <linux/gpio.h>

int native_gpio_open(const char *chip) {
    return open(chip, O_RDONLY);
}

int native_gpio_close(int fd) {
    return close(fd);
}

int native_gpio_line_request_output(int chip_fd, int line, int value) {
    struct gpiohandle_request req;
    memset(&req, 0, sizeof(req));
    req.lineoffsets[0] = line;
    req.flags = GPIOHANDLE_REQUEST_OUTPUT;
    req.default_values[0] = value;
    req.lines = 1;
    snprintf(req.consumer_label, sizeof(req.consumer_label), "vir");
    if (ioctl(chip_fd, GPIO_GET_LINEHANDLE_IOCTL, &req) < 0)
        return -1;
    return req.fd;
}

int native_gpio_line_request_input(int chip_fd, int line) {
    struct gpiohandle_request req;
    memset(&req, 0, sizeof(req));
    req.lineoffsets[0] = line;
    req.flags = GPIOHANDLE_REQUEST_INPUT;
    req.lines = 1;
    snprintf(req.consumer_label, sizeof(req.consumer_label), "vir");
    if (ioctl(chip_fd, GPIO_GET_LINEHANDLE_IOCTL, &req) < 0)
        return -1;
    return req.fd;
}

int native_gpio_set(int line_fd, int value) {
    struct gpiohandle_data data;
    data.values[0] = value;
    return ioctl(line_fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data);
}

int native_gpio_get(int line_fd) {
    struct gpiohandle_data data;
    if (ioctl(line_fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data) < 0)
        return -1;
    return data.values[0];
}

/* ═══════════════════════════════════════════════════════
 * §3  IoT – I2C (Linux /dev/i2c-* via ioctl)
 * ═══════════════════════════════════════════════════════ */

#include <linux/i2c.h>
#include <linux/i2c-dev.h>

int native_i2c_open(int bus) {
    char path[32];
    snprintf(path, sizeof(path), "/dev/i2c-%d", bus);
    return open(path, O_RDWR);
}

int native_i2c_close(int fd) {
    return close(fd);
}

int native_i2c_set_addr(int fd, int addr) {
    return ioctl(fd, I2C_SLAVE, addr);
}

int native_i2c_read_byte(int fd) {
    uint8_t buf;
    if (read(fd, &buf, 1) != 1) return -1;
    return buf;
}

int native_i2c_write_byte(int fd, int val) {
    uint8_t buf = (uint8_t)val;
    return (write(fd, &buf, 1) == 1) ? 0 : -1;
}

/* ═══════════════════════════════════════════════════════
 * §4  IoT – SPI (Linux /dev/spidev* via ioctl)
 * ═══════════════════════════════════════════════════════ */

#include <linux/spi/spidev.h>

int native_spi_open(int bus, int cs) {
    char path[32];
    snprintf(path, sizeof(path), "/dev/spidev%d.%d", bus, cs);
    return open(path, O_RDWR);
}

int native_spi_close(int fd) {
    return close(fd);
}

int native_spi_set_speed(int fd, uint32_t speed_hz) {
    return ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed_hz);
}

int native_spi_set_mode(int fd, uint8_t mode) {
    return ioctl(fd, SPI_IOC_WR_MODE, &mode);
}

int native_spi_transfer(int fd, const uint8_t *tx, uint8_t *rx, size_t len) {
    struct spi_ioc_transfer xfer;
    memset(&xfer, 0, sizeof(xfer));
    xfer.tx_buf = (unsigned long)tx;
    xfer.rx_buf = (unsigned long)rx;
    xfer.len = (uint32_t)len;
    return ioctl(fd, SPI_IOC_MESSAGE(1), &xfer);
}

/* ═══════════════════════════════════════════════════════
 * §5  IoT – Serial/UART (POSIX termios)
 * ═══════════════════════════════════════════════════════ */

#include <termios.h>

int native_serial_open(const char *path, int baud) {
    int fd = open(path, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) return -1;
    struct termios tty;
    memset(&tty, 0, sizeof(tty));
    if (tcgetattr(fd, &tty) != 0) { close(fd); return -1; }
    speed_t spd = B9600;
    if (baud == 115200) spd = B115200;
    else if (baud == 57600) spd = B57600;
    else if (baud == 38400) spd = B38400;
    else if (baud == 19200) spd = B19200;
    cfsetispeed(&tty, spd);
    cfsetospeed(&tty, spd);
    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
    tty.c_cflag |= CLOCAL | CREAD;
    tty.c_cflag &= ~(PARENB | PARODD | CSTOPB);
    tty.c_iflag &= ~(IXON | IXOFF | IXANY | IGNBRK);
    tty.c_lflag = 0;
    tty.c_oflag = 0;
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 5;
    tcsetattr(fd, TCSANOW, &tty);
    return fd;
}

int native_serial_close(int fd) {
    return close(fd);
}

int native_serial_write(int fd, const void *buf, size_t len) {
    return (int)write(fd, buf, len);
}

int native_serial_read(int fd, void *buf, size_t len) {
    return (int)read(fd, buf, len);
}

#else /* macOS / non-Linux stubs for IoT hardware */

/* GPIO stubs */
int native_gpio_open(const char *chip)   { (void)chip; return -1; }
int native_gpio_close(int fd)            { (void)fd;   return -1; }
int native_gpio_line_request_output(int chip_fd, int line, int value)
    { (void)chip_fd; (void)line; (void)value; return -1; }
int native_gpio_line_request_input(int chip_fd, int line)
    { (void)chip_fd; (void)line; return -1; }
int native_gpio_set(int line_fd, int value) { (void)line_fd; (void)value; return -1; }
int native_gpio_get(int line_fd)          { (void)line_fd; return -1; }

/* I2C stubs */
int native_i2c_open(int bus)              { (void)bus;  return -1; }
int native_i2c_close(int fd)              { (void)fd;   return -1; }
int native_i2c_set_addr(int fd, int addr) { (void)fd; (void)addr; return -1; }
int native_i2c_read_byte(int fd)          { (void)fd;   return -1; }
int native_i2c_write_byte(int fd, int val){ (void)fd; (void)val; return -1; }

/* SPI stubs */
int native_spi_open(int bus, int cs)      { (void)bus; (void)cs; return -1; }
int native_spi_close(int fd)              { (void)fd;   return -1; }
int native_spi_set_speed(int fd, uint32_t speed_hz) { (void)fd; (void)speed_hz; return -1; }
int native_spi_set_mode(int fd, uint8_t mode) { (void)fd; (void)mode; return -1; }
int native_spi_transfer(int fd, const uint8_t *tx, uint8_t *rx, size_t len)
    { (void)fd; (void)tx; (void)rx; (void)len; return -1; }

/* Serial — POSIX termios works on macOS too */
#include <termios.h>

int native_serial_open(const char *path, int baud) {
    int fd = open(path, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) return -1;
    struct termios tty;
    memset(&tty, 0, sizeof(tty));
    if (tcgetattr(fd, &tty) != 0) { close(fd); return -1; }
    speed_t spd = B9600;
    if (baud == 115200) spd = B115200;
    else if (baud == 57600) spd = B57600;
    else if (baud == 38400) spd = B38400;
    else if (baud == 19200) spd = B19200;
    cfsetispeed(&tty, spd);
    cfsetospeed(&tty, spd);
    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
    tty.c_cflag |= CLOCAL | CREAD;
    tty.c_cflag &= ~(PARENB | PARODD | CSTOPB);
    tty.c_iflag &= ~(IXON | IXOFF | IXANY | IGNBRK);
    tty.c_lflag = 0;
    tty.c_oflag = 0;
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 5;
    tcsetattr(fd, TCSANOW, &tty);
    return fd;
}

int native_serial_close(int fd) { return close(fd); }
int native_serial_write(int fd, const void *buf, size_t len) { return (int)write(fd, buf, len); }
int native_serial_read(int fd, void *buf, size_t len) { return (int)read(fd, buf, len); }

#endif /* __linux__ */

/* ═══════════════════════════════════════════════════════
 * §6  TLS – Native crypto backing
 * ═══════════════════════════════════════════════════════
 *
 * TLS requires a crypto library:
 *   - macOS:  Link with -lssl -lcrypto (OpenSSL via Homebrew)
 *   - Linux:  Link with -lssl -lcrypto (system OpenSSL)
 *
 * Without OpenSSL, these are stubs returning -1.
 * To enable real TLS: install OpenSSL, add -DVIR_HAS_OPENSSL
 * to CFLAGS, and link -lssl -lcrypto.
 */

#ifdef VIR_HAS_OPENSSL

#include <openssl/ssl.h>
#include <openssl/err.h>

typedef struct {
    SSL_CTX *ctx;
    SSL     *ssl;
    int      sockfd;
} vir_tls_t;

static int g_ssl_initialized = 0;

static void ensure_ssl_init(void) {
    if (!g_ssl_initialized) {
        SSL_library_init();
        SSL_load_error_strings();
        g_ssl_initialized = 1;
    }
}

void *native_tls_connect(int sockfd, const char *hostname) {
    ensure_ssl_init();
    vir_tls_t *tls = (vir_tls_t *)calloc(1, sizeof(vir_tls_t));
    if (!tls) return NULL;
    tls->sockfd = sockfd;
    tls->ctx = SSL_CTX_new(TLS_client_method());
    if (!tls->ctx) { free(tls); return NULL; }
    tls->ssl = SSL_new(tls->ctx);
    SSL_set_fd(tls->ssl, sockfd);
    if (hostname) SSL_set_tlsext_host_name(tls->ssl, hostname);
    if (SSL_connect(tls->ssl) <= 0) {
        SSL_free(tls->ssl);
        SSL_CTX_free(tls->ctx);
        free(tls);
        return NULL;
    }
    return tls;
}

int native_tls_read(void *handle, void *buf, size_t len) {
    if (!handle) return -1;
    return SSL_read(((vir_tls_t *)handle)->ssl, buf, (int)len);
}

int native_tls_write(void *handle, const void *buf, size_t len) {
    if (!handle) return -1;
    return SSL_write(((vir_tls_t *)handle)->ssl, buf, (int)len);
}

void native_tls_close(void *handle) {
    if (!handle) return;
    vir_tls_t *tls = (vir_tls_t *)handle;
    SSL_shutdown(tls->ssl);
    SSL_free(tls->ssl);
    SSL_CTX_free(tls->ctx);
    free(tls);
}

#else /* No OpenSSL — stubs */

void *native_tls_connect(int sockfd, const char *hostname)
    { (void)sockfd; (void)hostname; return NULL; }
int native_tls_read(void *h, void *buf, size_t len)
    { (void)h; (void)buf; (void)len; return -1; }
int native_tls_write(void *h, const void *buf, size_t len)
    { (void)h; (void)buf; (void)len; return -1; }
void native_tls_close(void *h) { (void)h; }

#endif /* VIR_HAS_OPENSSL */
