/* USB descriptors: a single CDC-ACM device ("DroneLoc Mic Array"). */
#include "tusb.h"
#include "pico/unique_id.h"
#include <string.h>

#define USB_VID 0x2E8A   /* Raspberry Pi */
#define USB_PID 0x000A   /* Pico SDK CDC: Windows/Linux/macOS load the serial driver automatically */

static const tusb_desc_device_t desc_device = {
    .bLength = sizeof(tusb_desc_device_t), .bDescriptorType = TUSB_DESC_DEVICE, .bcdUSB = 0x0200,
    .bDeviceClass = TUSB_CLASS_MISC, .bDeviceSubClass = MISC_SUBCLASS_COMMON, .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE, .idVendor = USB_VID, .idProduct = USB_PID, .bcdDevice = 0x0100,
    .iManufacturer = 1, .iProduct = 2, .iSerialNumber = 3, .bNumConfigurations = 1};

uint8_t const *tud_descriptor_device_cb(void) { return (uint8_t const *)&desc_device; }

enum { ITF_CDC = 0, ITF_CDC_DATA, ITF_TOTAL };
#define EP_CDC_NOTIF 0x81
#define EP_CDC_OUT   0x02
#define EP_CDC_IN    0x82
#define CONFIG_LEN   (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN)

static const uint8_t desc_config[] = {
    TUD_CONFIG_DESCRIPTOR(1, ITF_TOTAL, 0, CONFIG_LEN, 0x80, 250),
    TUD_CDC_DESCRIPTOR(ITF_CDC, 4, EP_CDC_NOTIF, 8, EP_CDC_OUT, EP_CDC_IN, 64),
};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) { (void)index; return desc_config; }

static char serial[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
static const char *strings[] = {(const char[]){0x09, 0x04}, "DroneLoc", "DroneLoc Mic Array", serial, "DroneLoc CDC"};
static uint16_t desc_str[32];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    uint8_t n;
    if (index == 0) { desc_str[1] = 0x0409; n = 1; }
    else {
        if (index >= sizeof(strings) / sizeof(strings[0])) return NULL;
        if (index == 3 && !serial[0]) pico_get_unique_board_id_string(serial, sizeof(serial));
        const char *s = strings[index];
        n = (uint8_t)strlen(s); if (n > 31) n = 31;
        for (uint8_t i = 0; i < n; i++) desc_str[1 + i] = s[i];
    }
    desc_str[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * n + 2));
    return desc_str;
}
