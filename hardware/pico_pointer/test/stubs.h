/* Host-side stand-ins for the pico-sdk / TinyUSB calls used by main.c (unit test only). */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
typedef uint64_t absolute_time_t;
typedef unsigned uint;
typedef struct { int d; } pwm_config;
#define GPIO_FUNC_PWM 4
#define GPIO_OUT 1
extern uint64_t now_us; extern int level[32]; extern char outbuf[4096];
static inline absolute_time_t get_absolute_time(void) { return now_us; }
static inline int64_t absolute_time_diff_us(absolute_time_t a, absolute_time_t b) { return (int64_t)(b - a); }
static inline uint32_t to_ms_since_boot(absolute_time_t t) { return (uint32_t)(t / 1000); }
static inline void gpio_init(uint p) { (void)p; }
static inline void gpio_set_dir(uint p, int d) { (void)p; (void)d; }
static inline void gpio_put(uint p, int v) { (void)p; (void)v; }
static inline void gpio_set_function(uint p, int f) { (void)p; (void)f; }
static inline uint pwm_gpio_to_slice_num(uint p) { return (p >> 1) & 7; }
static inline pwm_config pwm_get_default_config(void) { pwm_config c = {0}; return c; }
static inline void pwm_config_set_clkdiv(pwm_config *c, float d) { (void)c; (void)d; }
static inline void pwm_config_set_wrap(pwm_config *c, uint16_t w) { (void)c; (void)w; }
static inline void pwm_init(uint s, pwm_config *c, bool e) { (void)s; (void)c; (void)e; }
static inline void pwm_set_gpio_level(uint p, uint16_t l) { level[p] = l; }
static inline uint32_t clock_get_hz(int c) { (void)c; return 125000000; }
#define clk_sys 0
static inline void tusb_init(void) {}
static inline void tud_task(void) {}
static inline bool tud_cdc_available(void) { return false; }
static inline int tud_cdc_read_char(void) { return -1; }
static inline bool tud_cdc_connected(void) { return true; }
static inline void tud_cdc_write_str(const char *s) { strncat(outbuf, s, sizeof outbuf - strlen(outbuf) - 1); }
static inline void tud_cdc_write_flush(void) {}
