"""Read the low-cost Raspberry Pi Pico microphone array (hardware/pico_mic_array).

The Pico streams fixed-size packets over USB serial:

    "MICA" | u32 seq | u32 dropped | u16 nch | u16 nframes | u32 fs |
    nframes x nch x i16 (little endian, interleaved) | u16 checksum

checksum = sum of the i16 words (as unsigned) mod 65536. `PacketReader` resyncs on
the "MICA" magic, rejects packets with a bad checksum and counts lost packets
(sequence gaps) and frames the Pico dropped itself. Lost data are replaced by
zeros so that the channels stay time-aligned in the WAV file.
"""
from __future__ import annotations

import struct

import numpy as np

MAGIC = b"MICA"
HEADER = struct.Struct("<4sIIHHI")  # 20 bytes


def make_packet(seq: int, data: np.ndarray, fs: int = 15625, dropped: int = 0) -> bytes:
    """Build one packet (used by the tests; mirrors main.c)."""
    data = np.asarray(data, "<i2")
    nf, nch = data.shape
    body = data.tobytes()
    s = int(data.view("<u2").sum()) & 0xFFFF
    return HEADER.pack(MAGIC, seq & 0xFFFFFFFF, dropped, nch, nf, fs) + body + struct.pack("<H", s)


class PacketReader:
    """Feed raw bytes, get (seq, dropped, fs, frames[nf, nch] int16) for every valid packet."""

    def __init__(self):
        self.buf = bytearray()
        self.bad = 0          # packets rejected (checksum / header)
        self.lost = 0         # packets missing (sequence gaps)
        self.last_seq = None

    def feed(self, chunk: bytes):
        self.buf += chunk
        out = []
        while True:
            i = self.buf.find(MAGIC)
            if i < 0:
                del self.buf[:max(0, len(self.buf) - 3)]
                return out
            if i:
                del self.buf[:i]
            if len(self.buf) < HEADER.size:
                return out
            _, seq, dropped, nch, nf, fs = HEADER.unpack_from(self.buf)
            if not (1 <= nch <= 64 and 1 <= nf <= 1024 and 1000 <= fs <= 200000):
                self.bad += 1
                del self.buf[:1]
                continue
            n = HEADER.size + nf * nch * 2 + 2
            if len(self.buf) < n:
                return out
            raw = bytes(self.buf[HEADER.size:n - 2])
            (chk,) = struct.unpack_from("<H", self.buf, n - 2)
            if (int(np.frombuffer(raw, "<u2").sum()) & 0xFFFF) != chk:
                self.bad += 1
                del self.buf[:1]
                continue
            del self.buf[:n]
            if self.last_seq is not None:
                gap = (seq - self.last_seq - 1) & 0xFFFFFFFF
                if gap and gap < 1_000_000:
                    self.lost += gap
                    zeros = np.zeros((nf, nch), np.int16)
                    out += [(None, dropped, fs, zeros)] * min(gap, 10_000)
            self.last_seq = seq
            out.append((seq, dropped, fs, np.frombuffer(raw, "<i2").reshape(nf, nch).copy()))


def find_port() -> str | None:
    """Serial port of the first connected Pico (USB VID 0x2E8A)."""
    from serial.tools import list_ports
    for p in list_ports.comports():
        if p.vid == 0x2E8A:
            return p.device
    return None


def level_db(frames: np.ndarray) -> np.ndarray:
    """RMS level of each channel in dB re full scale."""
    x = frames.astype(float) / 32768.0
    x = x - x.mean(0)
    return 20 * np.log10(np.sqrt(np.mean(x ** 2, 0)) + 1e-9)
