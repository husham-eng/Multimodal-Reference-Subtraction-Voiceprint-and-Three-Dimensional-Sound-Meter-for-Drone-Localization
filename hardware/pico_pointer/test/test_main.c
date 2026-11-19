/* Unit test of the command logic of main.c on the host:  cc -Itest test/test_main.c -o t && ./t */
#include "stubs.h"
uint64_t now_us = 0; int level[32]; char outbuf[4096];
#define main fw_main
#include "../main.c"
#undef main
static int fails = 0;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
static void cmd(const char *s) { char b[96]; strcpy(b, s); outbuf[0] = 0; command(b); }
static void run(float seconds) { for (int k = 0; k < (int)(seconds * 100); k++) { now_us += 10000; update(0.01f, now_us); } }
int main(void) {
    pwm_setup();
    for (int i = 0; i < NCH; i++) CHECK(level[16 + i] == 0 && !ch[i].on);       /* released at power-up */
    cmd("S 0 1500"); CHECK(strstr(outbuf, "OK")); run(0.1f); CHECK(level[16] == 1500);
    cmd("S 0 2400"); CHECK(ch[0].target == 1800);                                  /* clamped to default limits */
    run(0.5f); CHECK(level[16] > 1500 && level[16] < 1800);                       /* slew limited: 300 us/s */
    run(1.0f); CHECK(level[16] == 1800);
    cmd("A 1 90"); run(0.1f); CHECK(level[17] == 1500);                           /* 90 deg = centre of 1200..1800 */
    cmd("LIM 1 1000 2000"); cmd("A 1 180"); CHECK(ch[1].target == 2000);
    cmd("LIM 1 2000 1000"); CHECK(strstr(outbuf, "ERR"));
    cmd("H U 0 180"); CHECK(ch[0].target == 1200 && ch[1].target == 2000);
    cmd("H Q 0 0"); CHECK(strstr(outbuf, "ERR"));
    cmd("S 7 1500"); CHECK(strstr(outbuf, "ERR"));
    cmd("X 0"); CHECK(!ch[0].on && level[16] == 0);
    cmd("X *"); for (int i = 0; i < NCH; i++) CHECK(!ch[i].on);
    cmd("T 2"); cmd("S 2 1500"); run(1.5f); CHECK(ch[2].on);
    run(1.0f); CHECK(!ch[2].on && level[18] == 0);                                /* watchdog released it */
    cmd("T 0"); cmd("S 3 1500"); run(10.0f); CHECK(ch[3].on);                     /* watchdog off */
    cmd("?"); CHECK(strstr(outbuf, "ch3 on=1"));
    printf(fails ? "%d FAILED\n" : "all firmware logic checks passed\n", fails);
    return fails != 0;
}
