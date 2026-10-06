/* 79-tap half-band low-pass (Kaiser beta 8 windowed sinc), Q13, DC gain exactly 1.
   Input 31250 Hz -> output 15625 Hz. Pass band to 6.9 kHz (-0.02 dB), stop band from 8.75 kHz (< -56 dB).
   Every second tap away from the centre is zero. Generated with numpy (see README). */
#pragma once
#include <stdint.h>
#define HB_TAPS 79
static const int32_t HB[HB_TAPS] = {0, 0, 1, 0, -1, 0, 3, 0, -5, 0, 8, 0, -12, 0, 19, 0, -27, 0, 39, 0, -53, 0, 73, 0, -98, 0, 131, 0, -175, 0, 237, 0, -330, 0, 490, 0, -850, 0, 2601, 4090, 2601, 0, -850, 0, 490, 0, -330, 0, 237, 0, -175, 0, 131, 0, -98, 0, 73, 0, -53, 0, 39, 0, -27, 0, 19, 0, -12, 0, 8, 0, -5, 0, 3, 0, -1, 0, 1, 0, 0};
