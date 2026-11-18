/*
 * DroneLoc pointer: Raspberry Pi Pico (RP2040) driving the two pan/tilt heads
 * (4 hobby servos, e.g. MG995) from text commands sent over USB serial.
 *
 *   channel 0 = GPIO 16 = upper head pan      channel 1 = GPIO 17 = upper head tilt
 *   channel 2 = GPIO 18 = lower head pan      channel 3 = GPIO 19 = lower head tilt
 *
 * Safety first (servos can tear their own wires):
 *   - at power-up every channel is RELEASED: no pulses, the servo is limp;
 *   - a channel only moves inside its limits [min_us, max_us], by default the
 *     narrow 1200..1800 us (about +-55 deg around the centre) until calibrated;
 *   - moves are slew-rate limited (default 300 us/s);
 *   - if no command arrives for `timeout` seconds (default 5) all channels are
 *     released.
 *
 * Commands (one per line, replies "OK ..." or "ERR ..."):
 *   ?                     status of all channels
 *   S <ch> <us>           go to a pulse width (clamped to the limits)
 *   A <ch> <deg>          go to an angle 0..180, mapped linearly onto min_us..max_us
 *   H <U|L> <pan> <tilt>  both servos of the upper (U) or lower (L) head, in degrees
 *   X <ch|*>              release (stop the pulses)
 *   LIM <ch> <min> <max>  set the limits in us (500..2500); the target is re-clamped
 *   RATE <us_per_s>       slew rate (10..5000)
 *   T <seconds>           watchdog timeout (0 = off)
 *   P                     ping (keeps the watchdog alive)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/clocks.h"
#include "tusb.h"

#define NCH       4
#define PIN_BASE  16
#define PIN_LED   25
#define ABS_MIN   500
#define ABS_MAX   2500

typedef struct {
    float cur, target;       /* pulse width [us] */
    int min_us, max_us;
    bool on;
} channel_t;

static channel_t ch[NCH];
static float rate = 300.0f;          /* us per second */
static uint32_t timeout_ms = 5000;
static absolute_time_t last_cmd;

static void out(const char *s) {
    tud_cdc_write_str(s);
    tud_cdc_write_str("\n");
    tud_cdc_write_flush();
}

static void pwm_setup(void) {
    /* 1 MHz PWM counter, 20 ms period: the compare level is the pulse width in us */
    float div = (float)clock_get_hz(clk_sys) / 1e6f;
    for (int i = 0; i < NCH; i++) {
        uint pin = PIN_BASE + i;
        gpio_set_function(pin, GPIO_FUNC_PWM);
        uint slice = pwm_gpio_to_slice_num(pin);
        pwm_config c = pwm_get_default_config();
        pwm_config_set_clkdiv(&c, div);
        pwm_config_set_wrap(&c, 19999);
        pwm_init(slice, &c, true);
        pwm_set_gpio_level(pin, 0);    /* released */
        ch[i] = (channel_t){1500.0f, 1500.0f, 1200, 1800, false};
    }
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

static void go(int i, float us) {
    if (us < ch[i].min_us) us = (float)ch[i].min_us;
    if (us > ch[i].max_us) us = (float)ch[i].max_us;
    if (!ch[i].on) ch[i].cur = us;     /* first command after release: no known position, start there */
    ch[i].target = us;
    ch[i].on = true;
}

static float deg_to_us(int i, float deg) {
    if (deg < 0) deg = 0;
    if (deg > 180) deg = 180;
    return ch[i].min_us + (ch[i].max_us - ch[i].min_us) * deg / 180.0f;
}

static void release(int i) {
    ch[i].on = false;
    pwm_set_gpio_level(PIN_BASE + i, 0);
}

static void status(void) {
    char b[96];
    for (int i = 0; i < NCH; i++) {
        snprintf(b, sizeof b, "OK ch%d on=%d us=%d target=%d lim=%d..%d", i, ch[i].on,
                 (int)ch[i].cur, (int)ch[i].target, ch[i].min_us, ch[i].max_us);
        out(b);
    }
    snprintf(b, sizeof b, "OK rate=%d timeout=%lu", (int)rate, (unsigned long)timeout_ms / 1000);
    out(b);
}

static void command(char *line) {
    char *tok[5] = {0};
    int n = 0;
    for (char *p = strtok(line, " \t\r"); p && n < 5; p = strtok(NULL, " \t\r")) tok[n++] = p;
    if (!n) return;
    last_cmd = get_absolute_time();
    char *c = tok[0];
    int i = n > 1 ? atoi(tok[1]) : -1;
    if (!strcmp(c, "?")) { status(); return; }
    if (!strcmp(c, "P")) { out("OK pong"); return; }
    if (!strcmp(c, "X") && n == 2) {
        if (tok[1][0] == '*') for (int k = 0; k < NCH; k++) release(k);
        else if (i >= 0 && i < NCH) release(i);
        else { out("ERR channel"); return; }
        out("OK released"); return;
    }
    if (!strcmp(c, "RATE") && n == 2) { rate = (float)clampi(atoi(tok[1]), 10, 5000); out("OK rate"); return; }
    if (!strcmp(c, "T") && n == 2) { timeout_ms = (uint32_t)clampi(atoi(tok[1]), 0, 3600) * 1000u; out("OK timeout"); return; }
    if (!strcmp(c, "H") && n == 4 && (tok[1][0] == 'U' || tok[1][0] == 'L')) {
        int b = tok[1][0] == 'U' ? 0 : 2;
        go(b, deg_to_us(b, (float)atof(tok[2])));
        go(b + 1, deg_to_us(b + 1, (float)atof(tok[3])));
        out("OK head"); return;
    }
    if (i < 0 || i >= NCH) { out("ERR channel"); return; }
    if (!strcmp(c, "S") && n == 3) { go(i, (float)atoi(tok[2])); out("OK servo"); return; }
    if (!strcmp(c, "A") && n == 3) { go(i, deg_to_us(i, (float)atof(tok[2]))); out("OK angle"); return; }
    if (!strcmp(c, "LIM") && n == 4) {
        int lo = clampi(atoi(tok[2]), ABS_MIN, ABS_MAX), hi = clampi(atoi(tok[3]), ABS_MIN, ABS_MAX);
        if (lo >= hi) { out("ERR limits"); return; }
        ch[i].min_us = lo; ch[i].max_us = hi;
        if (ch[i].on) go(i, ch[i].target);
        out("OK limits"); return;
    }
    out("ERR unknown command");
}

/* one 100 Hz step: move every driven channel towards its target; returns true if any is driven */
static bool update(float dt, absolute_time_t now) {
    bool any = false;
    for (int i = 0; i < NCH; i++) {
        if (!ch[i].on) continue;
        any = true;
        float step = rate * dt, d = ch[i].target - ch[i].cur;
        ch[i].cur += d > step ? step : (d < -step ? -step : d);
        pwm_set_gpio_level(PIN_BASE + i, (uint16_t)(ch[i].cur + 0.5f));
    }
    if (timeout_ms && any && absolute_time_diff_us(last_cmd, now) > (int64_t)timeout_ms * 1000) {
        for (int i = 0; i < NCH; i++) release(i);
        if (tud_cdc_connected()) out("OK timeout: all released");
        any = false;
    }
    return any;
}

int main(void) {
    gpio_init(PIN_LED); gpio_set_dir(PIN_LED, GPIO_OUT);
    pwm_setup();
    tusb_init();
    last_cmd = get_absolute_time();
    char line[96];
    int len = 0;
    absolute_time_t tick = get_absolute_time();
    for (;;) {
        tud_task();
        while (tud_cdc_available()) {
            char c = (char)tud_cdc_read_char();
            if (c == '\n') { line[len] = 0; command(line); len = 0; }
            else if (len < (int)sizeof line - 1) line[len++] = c;
        }
        absolute_time_t now = get_absolute_time();
        if (absolute_time_diff_us(tick, now) < 10000) continue;   /* 100 Hz update */
        float dt = absolute_time_diff_us(tick, now) * 1e-6f;
        tick = now;
        bool any = update(dt, now);
        /* LED: on while a servo is driven, slow blink otherwise */
        gpio_put(PIN_LED, any ? 1 : (to_ms_since_boot(now) / 1000) & 1);
    }
}
