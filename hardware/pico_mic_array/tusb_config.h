#pragma once
/* TinyUSB configuration: one CDC (virtual serial) interface with large
   buffers so that 12 channels x 15625 Hz x 16 bit (375 kB/s) stream freely. */
#define CFG_TUSB_RHPORT0_MODE   OPT_MODE_DEVICE
#ifndef CFG_TUSB_OS
#define CFG_TUSB_OS             OPT_OS_PICO
#endif
#define CFG_TUD_ENDPOINT0_SIZE  64
#define CFG_TUD_CDC             1
#define CFG_TUD_MSC             0
#define CFG_TUD_HID             0
#define CFG_TUD_MIDI            0
#define CFG_TUD_VENDOR          0
#define CFG_TUD_CDC_RX_BUFSIZE  64
#define CFG_TUD_CDC_TX_BUFSIZE  8192
#define CFG_TUD_CDC_EP_BUFSIZE  64
