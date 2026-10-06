/*
 * DroneLoc low-cost microphone array: Raspberry Pi Pico (RP2040) + up to
 * 12 INMP441 I2S MEMS microphones, all on ONE bit clock, streamed to a PC
 * over USB as a virtual serial port.
 *
 *   GPIO 8  -> SCK of every microphone      GPIO 9 -> WS of every microphone
 *   GPIO 2..7 <- SD (data) lines 0..5; each line is shared by two microphones,
 *   one with L/R tied to GND (left) and one with L/R tied to 3V3 (right).
 *
 *   channel 2*i   = line i, left microphone
 *   channel 2*i+1 = line i, right microphone
 *
 * Microphones run at 31250 Hz (SCK 2.0 MHz); a half-band filter decimates to
 * 15625 Hz, 16 bit, which is what is sent. Packet format (little endian):
 *   "MICA" | u32 seq | u32 dropped_frames | u16 nch | u16 nframes | u32 fs |
 *   nframes x nch x i16 | u16 checksum (sum of the i16 words, mod 65536)
 */
#include <string.h>
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "tusb.h"
#include "i2s_array.pio.h"
#include "halfband.h"

#define PIN_DATA0   2
#define N_LINES     6
#define NCH         (2 * N_LINES)
#define PIN_SCK     8          /* must match i2s_array.pio */
#define PIN_WS      9          /* must match i2s_array.pio */
#define PIN_LED     25
#define SYS_KHZ     128000     /* 128 MHz: SCK = 128 MHz / 32 / 2 = 2.0 MHz exactly */
#define FS_OUT      15625
#define GAIN_SHIFT  2          /* +12 dB: INMP441 -26 dBFS @ 94 dB SPL -> -14 dBFS; clips at ~108 dB SPL */
#define RING        2048       /* output frames buffered (131 ms) */
#define NF          64         /* frames per USB packet */
#define HB_LEN      128        /* filter history per channel (power of two >= HB_TAPS) */

static int16_t ring[RING][NCH];
static volatile uint32_t head, tail, dropped;

static PIO line_pio[N_LINES];
static uint line_sm[N_LINES];

/* ------------------------------------------------------------------ core 1 */
static void core1_capture(void) {
    static int32_t hist[NCH][HB_LEN];
    uint32_t n = 0;                       /* input frame counter */
    const int c = HB_TAPS / 2;
    for (;;) {
        /* one input frame: left word then right word of every line */
        for (int i = 0; i < N_LINES; i++) {
            for (int lr = 0; lr < 2; lr++) {
                uint32_t w = pio_sm_get_blocking(line_pio[i], line_sm[i]);
                int32_t s24 = ((int32_t)(w << 1)) >> 8;          /* edges 1..24 = 24-bit sample */
                hist[2 * i + lr][n & (HB_LEN - 1)] = s24 >> (8 - GAIN_SHIFT);
            }
        }
        n++;
        if (n & 1) continue;                  /* decimate by 2 */
        uint32_t h = head;
        if (h - tail >= RING) { dropped++; continue; }
        int16_t *out = ring[h & (RING - 1)];
        uint32_t m = n - 1 - c;               /* centre of the filter (newest index is n-1) */
        for (int ch = 0; ch < NCH; ch++) {
            const int32_t *x = hist[ch];
            int32_t acc = HB[c] * x[m & (HB_LEN - 1)];
            for (int k = 1; k <= c; k += 2)
                acc += HB[c + k] * (x[(m - k) & (HB_LEN - 1)] + x[(m + k) & (HB_LEN - 1)]);
            acc = (acc + (1 << 12)) >> 13;
            out[ch] = (int16_t)(acc > 32767 ? 32767 : acc < -32768 ? -32768 : acc);
        }
        __dmb();
        head = h + 1;
    }
}

/* ------------------------------------------------------------------ setup */
static void start_pio(void) {
    PIO p0 = pio0, p1 = pio1;
    uint off_clk = pio_add_program(p0, &i2s_clock_program);
    uint off_l0 = pio_add_program(p0, &i2s_line_program);
    uint off_l1 = pio_add_program(p1, &i2s_line_program);

    for (int i = 0; i < N_LINES; i++) {
        PIO p = i < 3 ? p0 : p1;
        uint sm = i < 3 ? (uint)(i + 1) : (uint)(i - 3);
        uint off = i < 3 ? off_l0 : off_l1;
        uint pin = PIN_DATA0 + i;
        pio_sm_claim(p, sm);
        gpio_pull_down(pin);                         /* lines are tri-stated half of the time */
        pio_sm_set_consecutive_pindirs(p, sm, pin, 1, false);
        pio_sm_config c = i2s_line_program_get_default_config(off);
        sm_config_set_in_pins(&c, pin);
        sm_config_set_in_shift(&c, false, true, 32);  /* shift left, autopush 32 */
        sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_RX);
        sm_config_set_clkdiv(&c, 1.0f);
        pio_sm_init(p, sm, off, &c);
        line_pio[i] = p; line_sm[i] = sm;
    }

    uint sm_clk = 0;
    pio_sm_claim(p0, sm_clk);
    pio_gpio_init(p0, PIN_SCK); pio_gpio_init(p0, PIN_WS);
    gpio_set_drive_strength(PIN_SCK, GPIO_DRIVE_STRENGTH_12MA);
    gpio_set_drive_strength(PIN_WS, GPIO_DRIVE_STRENGTH_12MA);
    gpio_set_slew_rate(PIN_SCK, GPIO_SLEW_RATE_FAST);
    pio_sm_set_pins_with_mask(p0, sm_clk, 0, (1u << PIN_SCK) | (1u << PIN_WS));
    pio_sm_set_consecutive_pindirs(p0, sm_clk, PIN_SCK, 2, true);
    pio_sm_config cc = i2s_clock_program_get_default_config(off_clk);
    sm_config_set_sideset_pins(&cc, PIN_SCK);
    sm_config_set_clkdiv_int_frac(&cc, (uint16_t)(SYS_KHZ * 1000u / 4000000u), 0);  /* 4 MHz -> 2 MHz SCK */
    pio_sm_init(p0, sm_clk, off_clk + i2s_clock_offset_start, &cc);

    for (int i = 0; i < N_LINES; i++) pio_sm_set_enabled(line_pio[i], line_sm[i], true);
    pio_sm_set_enabled(p0, sm_clk, true);
}

/* ------------------------------------------------------------------ core 0 */
static uint8_t pkt[22 + NF * NCH * 2];

static void put16(uint8_t *b, uint16_t v) { b[0] = (uint8_t)v; b[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *b, uint32_t v) { put16(b, (uint16_t)v); put16(b + 2, (uint16_t)(v >> 16)); }

int main(void) {
    set_sys_clock_khz(SYS_KHZ, true);
    gpio_init(PIN_LED); gpio_set_dir(PIN_LED, GPIO_OUT);
    tusb_init();
    start_pio();
    multicore_launch_core1(core1_capture);

    uint32_t seq = 0;
    bool was_connected = false;
    for (;;) {
        tud_task();
        bool conn = tud_cdc_connected();
        if (!conn) { tail = head; was_connected = false; gpio_put(PIN_LED, (to_ms_since_boot(get_absolute_time()) / 500) & 1); continue; }
        if (!was_connected) { tail = head; was_connected = true; gpio_put(PIN_LED, 1); }
        if (head - tail < NF || tud_cdc_write_available() < sizeof(pkt)) continue;

        memcpy(pkt, "MICA", 4);
        put32(pkt + 4, seq++); put32(pkt + 8, dropped);
        put16(pkt + 12, NCH); put16(pkt + 14, NF); put32(pkt + 16, FS_OUT);
        uint16_t sum = 0;
        uint8_t *d = pkt + 20;
        for (int f = 0; f < NF; f++) {
            const int16_t *fr = ring[(tail + f) & (RING - 1)];
            for (int ch = 0; ch < NCH; ch++) { put16(d, (uint16_t)fr[ch]); sum += (uint16_t)fr[ch]; d += 2; }
        }
        __dmb();
        tail += NF;
        put16(d, sum);
        tud_cdc_write(pkt, sizeof(pkt));
        tud_cdc_write_flush();
        if ((seq & 255) == 0) gpio_xor_mask(1u << PIN_LED);   /* blink while streaming */
    }
}
