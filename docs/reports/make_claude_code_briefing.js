const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
        ShadingType, BorderStyle, ImageRun, LevelFormat, PageBreak, Footer, PageNumber } = require('docx');
const FIG = '/home/user/drone/docs/figures_ar/', HW = '/home/user/drone/hardware/pico_mic_array/';
const F = 'Arial', MONO = 'Consolas';

// ---- inline runs: string | {t, b, i, code, c}
const run = (s, base = {}, rtl = false) => typeof s === 'string'
  ? new TextRun({ text: s, font: F, rightToLeft: rtl, ...base })
  : new TextRun({ text: s.t, bold: s.b, italics: s.i, color: s.c, font: s.code ? MONO : F, rightToLeft: rtl && !s.code, ...base });
const runs = (x, base, rtl) => (Array.isArray(x) ? x : [x]).map(s => run(s, base, rtl));
const P = (x, o = {}) => new Paragraph({ spacing: { after: 120, line: 288 }, ...o, children: runs(x) });
const AR = (x, o = {}) => new Paragraph({ bidirectional: true, alignment: AlignmentType.RIGHT, spacing: { after: 140, line: 320 }, ...o, children: runs(x, { size: 24 }, true) });
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(t) });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(t) });
const H3 = t => new Paragraph({ heading: HeadingLevel.HEADING_3, children: runs(t) });
const B = (x, lvl = 0) => new Paragraph({ numbering: { reference: 'bul', level: lvl }, spacing: { after: 60, line: 276 }, children: runs(x) });
const ARB = x => new Paragraph({ bidirectional: true, alignment: AlignmentType.RIGHT, numbering: { reference: 'bulr', level: 0 }, spacing: { after: 80, line: 320 }, children: runs(x, { size: 24 }, true) });
let numCount = 0;
const numRefs = [];
function NUMLIST(items) { const ref = 'n' + (numCount++); numRefs.push(ref);
  return items.map(x => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 276 }, children: runs(x) })); }
const CODE = lines => lines.map((l, k) => new Paragraph({ spacing: { after: 0, before: k ? 0 : 60 },
  shading: { type: ShadingType.CLEAR, fill: 'F2F2F2', color: 'auto' }, children: [new TextRun({ text: l || ' ', font: MONO, size: 18 })] }));
const SP = () => new Paragraph({ spacing: { after: 60 }, children: [] });
const c = t => ({ t, code: true }), b = t => ({ t, b: true });
function IMG(file, wpx, caption) {
  const buf = fs.readFileSync(file), w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, keepNext: true,
            children: [new ImageRun({ type: 'png', data: buf, transformation: { width: wpx, height: Math.round(wpx * h / w) } })] }),
          P([{ t: caption, b: true, c: '444444' }], { alignment: AlignmentType.CENTER, spacing: { after: 200 } })];
}
const bd = { style: BorderStyle.SINGLE, size: 4, color: 'BBBBBB' };
function TABLE(head, rows, widths) {
  const cell = (x, i, hdr) => new TableCell({ width: { size: widths[i], type: WidthType.DXA }, margins: { top: 50, bottom: 50, left: 90, right: 90 },
    borders: { top: bd, bottom: bd, left: bd, right: bd }, shading: hdr ? { type: ShadingType.CLEAR, fill: 'DDE7F3', color: 'auto' } : undefined,
    children: [new Paragraph({ children: runs(x, hdr ? { bold: true, size: 19 } : { size: 19 }) })] });
  return new Table({ width: { size: widths.reduce((a, v) => a + v), type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: head.map((h, i) => cell(h, i, true)) }),
           ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((x, i) => cell(x, i, false)) }))] });
}
const body = [];
const add = (...xs) => xs.forEach(x => Array.isArray(x) ? body.push(...x) : body.push(x));

// ======================================================= Arabic cover note
add(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 160 }, children: runs(b('Briefing for Claude Code on the Raspberry Pi'), { size: 40, color: '1F3864' }) }));
add(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: runs('Acoustic drone localization — hardware bring-up: microphone array, camera, pan/tilt pointer', { size: 24, color: '555555' }) }));
add(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: runs('Prepared 29 October 2026 · repository husham-eng/Multimodal-Reference-Subtraction-Voiceprint-and-Three-Dimensional-Sound-Meter-for-Drone-Localization · branch claude/epic-ride-9fqd2p', { size: 18, color: '777777' }) }));
add(new Paragraph({ bidirectional: true, alignment: AlignmentType.RIGHT, spacing: { after: 160 }, children: runs(b('ملاحظة لك (د. هشام):'), { size: 28, color: '1F3864' }, true) }));
add(AR('هذا الملف موجّه إلى Claude Code الذي سيعمل على الراسبيري باي بعد أن تُكمل بناء الدائرة. يشرح له كل ما أُضيف: الدائرة، والأطراف، والبرامج، وما جُرّب وما لم يُجرَّب بعد، وخطوات التشغيل والاختبار. بهذا لا تحتاج أن تشرح من جديد.'));
add(AR('الجزء التقني مكتوب بالإنجليزية لأن Claude Code يتعامل معها بأعلى دقة، خصوصاً مع أسماء الأطراف والأوامر. وهو يفهم العربية، فاكتب له طلباتك بالعربية كالمعتاد.'));
add(AR([b('طريقة الاستخدام:')]));
add(ARB('شغّل Claude Code في مجلد المشروع على الباي:'));
add(CODE(['cd "/home/pi/Desktop/The Dron Project/code"', 'claude']));
add(SP());
add(ARB('لا تحتاج رفع الملف يدوياً: بعد تحديث الكود (القسم 2.3) ستجد نسخة نصية منه داخل المشروع، وهي أسهل على Claude Code من ملف الوورد. اكتب له:'));
add(CODE(['Read docs/reports/Claude_Code_Briefing.md, then help me bring up the circuit.']));
add(SP());
add(ARB(['تنبيه: Claude Code يحتاج نظاماً 64-بت، ونظام الباي الحالي 32-بت (armhf). إما أن تثبّت Raspberry Pi OS (64-bit) على بطاقة جديدة، أو تستخدم Claude Code على حاسوب آخر وتنفّذ الأوامر على الباي يدوياً.']));
add(ARB('قبل أي شيء على الباي: حدّث الكود بهذه الأوامر، لأن تاريخ الفرع على GitHub أُعيد ترتيبه فلن يعمل الأمر المعتاد git pull:'));
add(CODE(['cd "/home/pi/Desktop/The Dron Project/code"', 'git fetch origin', 'git reset --hard origin/claude/epic-ride-9fqd2p']));
add(new Paragraph({ children: [new PageBreak()] }));

// ======================================================= 1
add(H1('1. Read this first'));
add(P('You are helping Dr. Husham Saied (the user) bring up the hardware of an acoustic drone-localization project on a Raspberry Pi. The user prefers replies in Arabic (right-to-left text, commands in code blocks). Keep explanations short and practical: they build and wire the hardware themselves and paste terminal output back to you.'));
add(P(b('Ground rules:')));
add(B(['The software side is written and tested in simulation; ', b('none of the firmware has run on real hardware yet'), '. Expect bring-up issues and debug them step by step, starting with two microphones.']));
add(B(['Do not change the exact estimation path that produced the published results (', c('main'), ' = release 2.1.0, Zenodo DOI 10.5281/zenodo.23151340). Speed-ups for the Pi go behind options such as ', c('PhaseSRP(fast=True)'), ', which only the live mode uses.']));
add(B(['Keep the code Python 3.9 compatible and working on 32-bit ARM (the current Pi OS is armhf).']));
add(B(['Run ', c('python -m pytest tests'), ' after changes (22 tests; about 4 minutes on the Pi).']));
add(B(['Safety: laser below 1 mW (class 2), indoor bench tests only, never towards people, aircraft or drones in flight; servos on their own 5 V supply.']));

// ======================================================= 2
add(H1('2. Project and computer'));
add(H2('2.1 What the project does'));
add(P('A six-microphone rigid sphere (160 mm diameter, microphones at ±x, ±y, ±z) estimates the 3D direction of a drone from its rotor sound, so that a battery-swap station can guide the drone in. The processing chain: reference subtraction (reference microphones near the rotors and the station machinery train a multichannel Wiener canceller in a target-free window), voiceprint (blade-passing frequency, BPF, and its harmonics), and the 3D sound meter (GCC-PHAT / SRP with rigid-sphere steering, range from the calibrated level, Kalman tracking).'));
add(P(['Python package ', c('droneloc/'), '; command line ', c('python -m droneloc {libraries,run,evaluate-array,coherence,dregon,sphere-geometry,live}'), '.']));
add(H2('2.2 The Raspberry Pi'));
add(TABLE(['Item', 'Value'], [
  ['Project folder', [c('/home/pi/Desktop/The Dron Project/code'), ' (quote it: the path has spaces)']],
  ['Virtual environment', c('source .venv/bin/activate')],
  ['OS', 'Raspberry Pi OS, 32-bit userland (armhf) on a 64-bit kernel (uname -m = aarch64, getconf LONG_BIT = 32)'],
  ['Python', '3.9.2'],
  ['System packages installed', c('libsndfile1 libopenblas-dev')],
  ['Python packages', ['requirements.txt + pyserial; Pillow installed with ', c('pip install --only-binary=:all: pillow')]],
  ['Git', [c('git config pull.ff only'), ' is set']],
  ['Speed', 'About 10–20x slower than a laptop on every processing step'],
], [2600, 7000]));
add(H2('2.3 Updating the code on the Pi (history was rewritten)'));
add(P(['On 24 October 2026 the branch history on GitHub was rewritten (the journal submission files were removed from the public history). A plain ', c('git pull'), ' therefore fails on the Pi. Update with:']));
add(CODE(['cd "/home/pi/Desktop/The Dron Project/code"', 'git fetch origin', 'git reset --hard origin/claude/epic-ride-9fqd2p',
          'source .venv/bin/activate', 'python -m pytest tests']));
add(SP());
add(P(['Untracked files such as ', c('live.wav'), ' (a simulated test recording) are not affected. Do not re-add the removed submission files or the old ', c('docs/NEXT_SESSION.md'), '.']));

// ======================================================= 3
add(H1('3. Hardware architecture'));
add(P('Two Raspberry Pi Pico boards (RP2040), each on its own USB cable to the Raspberry Pi. There are no other wires between the Picos and the Pi, or between the two Picos. Each Pico is powered by its USB cable; the servos and the laser have a separate 5 V supply whose ground is joined to the ground of Pico 2.'));
add(...IMG(FIG + 'system_overview.png', 600, 'Figure 1. System overview (labels in Arabic).'));
add(TABLE(['', 'Pico 1 – audio', 'Pico 2 – camera and pointer'], [
  ['Firmware', [c('hardware/pico_mic_array/pico_mic_array.uf2'), ' (built, not yet run on hardware)'], b('Not written yet (section 6)')],
  ['USB product name', c('DroneLoc Mic Array'), [c('DroneLoc Pointer'), ' (planned)']],
  ['To the Pi', '12 audio channels, 15625 Hz, int16 (375 kB/s)', 'Camera frames, 160x120 grayscale, ~10–15 fps'],
  ['From the Pi', 'Nothing (streams while the port is open, DTR set)', 'Pan/tilt angles, laser on/off'],
  ['Attached', '12 x INMP441 I2S microphones', 'OV7670 camera (no FIFO, 18 pins), 2 x MG995 servos, laser < 1 mW'],
], [1900, 3850, 3850]));
add(SP());
add(P([b('Port detection: '), c('droneloc.pico.find_port(product="DroneLoc Mic Array")'), ' picks the port by USB product name and falls back to the first Raspberry Pi vendor id (0x2E8A) port. Give Pico 2 a different product string so the two are never confused.']));
add(P([b('Parts: '), 'the user ordered the INMP441 microphones (expected around 1 November 2026) and a Raspberry Pi Pico (RP2040, without soldered headers: the 2 x 20 header strips must be soldered). They own an OV7670 (no-FIFO, 18-pin) camera. The user chose MG995 servos (the camera and laser add weight); the pan/tilt bracket and laser are still to be bought. An Adafruit BNO085 IMU (product 4754) was considered for a later phase (array orientation) and is not part of this bring-up.']));

// ======================================================= 4
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('4. Pico 1: the 12-microphone array'));
add(H2('4.1 Wiring'));
add(P('All microphones share one bit clock (SCK) and one word select (WS) generated by the Pico, so the 12 channels are sample-synchronous (required: about 20 ppm clock skew between channels already breaks the reference canceller in simulation). Each data line (SD) carries two microphones; the L/R pin selects the slot (GND = left = even channel, 3V3 = right = odd channel). The microphone that is not in its slot leaves SD in high impedance.'));
add(...IMG(HW + 'wiring.png', 430, 'Figure 2. Wiring of Pico 1 with 12 INMP441 microphones (hardware/pico_mic_array/wiring.png).'));
add(...IMG(FIG + 'pins_diagram.png', 600, 'Figure 3. Pico pinout with the used pins, INMP441 pins, and two microphones sharing one SD line.'));
add(TABLE(['Pico pin', 'GPIO', 'Signal', 'Connects to'], [
  ['4', 'GP2', 'SD1', 'SD of channels 0, 1'], ['5', 'GP3', 'SD2', 'SD of channels 2, 3'], ['6', 'GP4', 'SD3', 'SD of channels 4, 5'],
  ['7', 'GP5', 'SD4', 'SD of channels 6, 7'], ['9', 'GP6', 'SD5', 'SD of channels 8, 9'], ['10', 'GP7', 'SD6', 'SD of channels 10, 11'],
  ['11', 'GP8', 'SCK (2.0 MHz)', 'SCK of all 12 microphones'], ['12', 'GP9', 'WS (31.25 kHz)', 'WS of all 12 microphones'],
  ['36', '3V3(OUT)', '3.3 V', 'VDD of all microphones; L/R of odd channels'],
  ['38 (any GND)', 'GND', 'Ground', 'GND of all microphones; L/R of even channels'],
], [1500, 1400, 2200, 4500]));
add(SP());
add(TABLE(['Channel', 'Role', 'SD line', 'L/R'], [
  ['0', 'Sphere +x', 'GP2', 'GND'], ['1', 'Sphere −x', 'GP2', '3V3'], ['2', 'Sphere +y', 'GP3', 'GND'], ['3', 'Sphere −y', 'GP3', '3V3'],
  ['4', 'Sphere +z (top)', 'GP4', 'GND'], ['5', 'Sphere −z (bottom)', 'GP4', '3V3'], ['6', 'Rotor reference 1', 'GP5', 'GND'],
  ['7', 'Rotor reference 2', 'GP5', '3V3'], ['8', 'Rotor reference 3', 'GP6', 'GND'], ['9', 'Rotor reference 4', 'GP6', '3V3'],
  ['10', 'Station (machinery) reference', 'GP7', 'GND'], ['11', 'Spare', 'GP7', '3V3'],
], [1300, 4300, 2000, 2000]));
add(SP());
add(P(['Geometry file of the sphere (channel order +x, −x, +y, −y, +z, −z; radius 80 mm): ', c('python -m droneloc sphere-geometry sphere.csv'), '. Array frame: x forward, y left, z up; azimuth = atan2(y, x).']));
add(P([b('Wiring rules: '), 'SCK/WS wires shorter than 20 cm (else 33–100 Ω in series at the Pico); unplug USB while rewiring; never connect 5 V to a microphone; INMP441 draws about 1.4 mA, 12 of them about 17 mA from 3V3(OUT).']));
add(H2('4.2 Firmware (hardware/pico_mic_array)'));
add(B(['System clock 128 MHz; one PIO state machine generates SCK (2.0 MHz) and WS by side-set (64 SCK per frame, 31250 frames/s); six PIO state machines sample the six SD lines on each rising SCK edge (7 of the 8 PIO state machines are used).']));
add(B(['Core 1: 24-bit samples, 79-tap half-band filter (stop band > 56 dB), decimation 2:1 to 15625 Hz, +12 dB gain (INMP441 −26 dBFS at 94 dB SPL becomes −14 dBFS; clipping near 108 dB SPL), int16, ring buffer of 2048 frames. Usable band up to about 6.9 kHz.']));
add(B(['Core 0: USB CDC packets of 64 frames x 12 channels: ', c('"MICA" | u32 seq | u32 dropped | u16 nch | u16 nframes | u32 fs | int16 data | u16 checksum'), ' (checksum = sum of the int16 words mod 65536). ', c('droneloc/pico.py PacketReader'), ' resyncs on the magic, rejects bad checksums and zero-fills lost packets so channels stay aligned.']));
add(B(['LED (GP25): blinks once per second while waiting for the host; on or toggling while streaming. The Pico only streams while the serial port is open with DTR set.']));
add(B(['USB VID 0x2E8A, PID 0x000A, product "DroneLoc Mic Array". Rebuild: pico-sdk ≥ 2.0 + arm-none-eabi-gcc (', c('mkdir build && cd build && cmake -DPICO_SDK_PATH=... .. && make'), ').']));
add(H2('4.3 Bring-up procedure'));
add(...NUMLIST([
  ['Flash: hold BOOTSEL, plug in USB, release; a drive RPI-RP2 appears; ', c('cp hardware/pico_mic_array/pico_mic_array.uf2 /media/pi/RPI-RP2/'), '.'],
  ['Check: LED blinks once per second; ', c('lsusb'), ' shows 2e8a:000a; ', c('/dev/ttyACM0'), ' exists.'],
  ['Wire only channels 0 and 1 (GP2; L/R to GND and to 3V3) and run ', c('python experiments/record_pico.py --check'), '.'],
  ['Expected: channels 0 and 1 about −70 to −55 dBFS in silence and −40 to −20 dBFS when speaking close by; unconnected channels about −90 or lower; "lost 0 bad 0".'],
  ['Add microphone pairs one SD line at a time, checking levels each time; then record: ', c('python experiments/record_pico.py --seconds 30 --out run01.wav'), '.'],
  ['Synchronisation check: tap the sphere or clap at a known side; the channel facing the sound should lead (inspect run01.wav), and ', c('python -m droneloc evaluate-array'), ' with a loudspeaker at known directions should give small errors.'],
  ['Live: ', c('python -m droneloc live --refs 6,7,8,9,10 --cal 3 --bpf 105,200 --steering sphere --hop 0.5 --log live.csv'), ' (keep the target away during the 3 s calibration).'],
]));
add(H2('4.4 Troubleshooting'));
add(TABLE(['Symptom', 'Likely cause / action'], [
  ['"Pico not found"', 'No Pico on USB, wrong firmware, or a charge-only cable. lsusb: 2e8a:0003 = still in BOOTSEL (copy the .uf2 again); no 2e8a at all = try another cable/port.'],
  ['/dev/ttyACM0 exists but "Permission denied"', ['User not in the dialout group: ', c('sudo usermod -aG dialout pi'), ', then log out and in.']],
  ['A channel at about −90 dBFS', 'Microphone not powered, SD on the wrong GPIO, or both microphones of a pair on the same L/R level.'],
  ['Both channels of a pair noisy / identical / garbage', 'L/R wrong (both on the same slot) – they fight on the shared SD line.'],
  ['Clipping (near 0 dBFS) at normal sound levels', 'Gain too high for the setup: reduce GAIN_SHIFT in main.c and rebuild.'],
  ['"lost" or "dropped" counters grow', 'USB bandwidth / host load: direct USB port (no hub), close other programs.'],
  ['Wrong directions, consistently mirrored or rotated', 'Channel order or sphere axes do not match the geometry (channel 0 must face +x, etc.).'],
], [3300, 6300]));

// ======================================================= 5
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('5. Live mode (software already written)'));
add(P([c('python -m droneloc live'), ' (', c('droneloc/live.py'), ') reads the Pico USB stream (or a WAV file cut into the same packets with ', c('--wav'), ', paced like the real device with ', c('--realtime'), '). It trains the reference canceller on the first ', c('--cal'), ' seconds, then every ', c('--hop'), ' seconds (default 0.25) estimates the direction from the last ', c('--window'), ' seconds (default 0.5): reference cancellation (time domain, 2048-sample STFT, with 2048 samples of history so its edges fall outside the window) → BPF estimate → GCC-PHAT cross-spectra → PhaseSRP with sphere steering. It prints time, level (dBFS), azimuth, elevation, peak power and BPF; ', c('--log'), ' writes a CSV.']));
add(TABLE(['Option', 'Meaning'], [
  [c('--port'), 'Serial port (default: the Pico named "DroneLoc Mic Array")'], [c('--wav / --realtime'), 'Replay a recording instead of the Pico'],
  [c('--geometry / --array'), 'Geometry CSV and array channel indices (default: 160 mm sphere, channels 0–5)'],
  [c('--refs 6,7,8,9,10 / --cal 3'), 'Reference channels and calibration time'],
  [c('--bpf 105,200'), 'BPF search range (rotor comb); or --band lo,hi for a beacon / broadband source'],
  [c('--steering sphere'), 'Rigid-sphere steering instead of free field'],
  [c('--window 0.5 / --hop 0.25'), 'Analysis window and time between estimates'], [c('--seconds / --log'), 'Stop time and CSV log'],
], [3000, 6600]));
add(SP());
add(P([b('Raspberry Pi performance '), '(32-bit OS, two reference channels, measured with ', c('python experiments/profile_live.py live.wav'), '): 244 ms per estimate (reference cancellation 97, cross-spectra 66, cap phases 35, cap power 22, grid 16 ms), startup 3.0 s. With five references cancellation is slower, so start with ', c('--hop 0.5'), '. If the computer falls behind, only the newest window is processed ("skipped N" in the output), so the delay stays bounded.']));
add(P([b('Accuracy in simulation: '), 'median error below 1° without machinery noise; with 80 dB station machinery all estimates after calibration within 3° (146° without the reference microphones). At 90–95 dB machinery the canceller (about 27 dB) is not enough.']));
add(P([b('Tried and rejected: '), 'cancelling directly in the GCC STFT domain without overlap-add resynthesis (145° error, as bad as no cancellation).']));

// ======================================================= 6
add(H1('6. Pico 2: camera and pan/tilt laser pointer (to be implemented)'));
add(P('Purpose: visual and quantitative check of the acoustic direction estimate, and a tool to calibrate the array alignment. The pan/tilt head points along the estimated direction; indoors a laser dot shows where the system thinks a loudspeaker is; a camera on the same head shows whether the source is at the image centre, and the pixel offset gives the error in degrees. Outdoors the laser is useless (the dot is invisible against the sky) and must not be aimed at aircraft or drones: use the camera only.'));
add(...IMG(FIG + 'pico2_camera_wiring.png', 600, 'Figure 4. Pico 2 wiring: OV7670 (no FIFO), pan/tilt servos and laser.'));
add(H2('6.1 Pin assignment'));
add(TABLE(['Pico pin', 'GPIO', 'Signal', 'Notes'], [
  ['1, 2, 4, 5, 6, 7, 9, 10', 'GP0–GP7', 'OV7670 D0–D7', 'Consecutive GPIOs, read by one PIO program'],
  ['11', 'GP8', 'PCLK (camera → Pico)', 'Pixel clock'], ['12', 'GP9', 'HREF', 'Line valid'], ['14', 'GP10', 'VSYNC', 'Frame start'],
  ['27', 'GP21', 'XCLK (Pico → camera)', 'Clock output (GPOUT0), 12–24 MHz'],
  ['16', 'GP12', 'SIOD (SCCB data)', '4.7 kΩ pull-up to 3.3 V; I2C0 SDA'], ['17', 'GP13', 'SIOC (SCCB clock)', '4.7 kΩ pull-up to 3.3 V; I2C0 SCL'],
  ['19', 'GP14', 'RESET (active low)', ''], ['—', 'GND', 'PWDN (active high)', 'Tied to GND: always on'],
  ['36 / 38', '3V3(OUT) / GND', 'Camera 3V3 / GND', 'The camera is 3.3 V only'],
  ['21', 'GP16', 'Pan servo signal', 'Hardware PWM, 50 Hz'], ['22', 'GP17', 'Tilt servo signal', 'Hardware PWM, 50 Hz'],
  ['24', 'GP18', 'Laser enable', '1 kΩ to the base of an NPN (2N2222/S8050); laser (−) to collector, (+) to 5 V'],
  ['23', 'GND', 'Common ground', 'Joined to the GND of the 5 V servo supply'],
], [1900, 1500, 2400, 3800]));
add(SP());
add(P([b('Power: '), 'servos and laser from a separate 5 V / 5 A supply with a 1000 µF capacitor across it (two MG995 can draw 2–3 A each when starting or stalled); never from the Pico or the Raspberry Pi. Camera wires shorter than 15 cm (PCLK, XCLK, D0–D7). Connect camera pins by the names printed on the board: the physical order varies between makers.']));
add(H3('MG995 servos (chosen by the user because of the camera and laser weight)'));
add(TABLE(['Property', 'Typical value (check the seller page)', 'Consequence'], [
  ['Supply', '4.8–7.2 V', 'Run at 5 V together with the laser (one 5 V / 5 A supply)'],
  ['Stall torque', 'about 8.5 kg·cm at 4.8 V, about 10 kg·cm at 6 V', 'Plenty for a small camera and laser'],
  ['Current', 'a few hundred mA moving, up to about 2–2.5 A starting or stalled', '5 A supply, 1000 µF capacitor, thick power wires'],
  ['Speed', 'about 0.2 s per 60°', 'Rate-limit commands; a full sweep takes ~0.6 s'],
  ['Size / weight', 'about 40 x 20 x 43 mm, 55 g', 'Standard-size bracket, not the SG90/MG90S kit'],
  ['Range', 'nominally 180°, many units give less (about 120–170°)', 'Measure the real range: the hemisphere mapping in 6.3 needs 180° on both axes'],
  ['Signal', '50 Hz PWM, about 500–2500 µs; analog servo with a noticeable dead band and some jitter', 'Calibrate the end points per servo; 3.3 V Pico signal usually works, else add a level shifter'],
], [1900, 3900, 3800]));
add(SP());
add(H2('6.2 Firmware to write (hardware/pico_pointer/)'));
add(B(['USB CDC device, VID 0x2E8A, product string ', c('"DroneLoc Pointer"'), '.']));
add(B(['Camera: XCLK from GPOUT0 on GP21 (e.g. ~12 MHz); configure over SCCB (I2C, 7-bit address 0x21) using a known-good OV7670 register table from an open-source project, QQVGA 160x120 YUV422; a PIO program waits for VSYNC/HREF and samples D0–D7 on rising PCLK; DMA into a frame buffer; keep only the Y bytes (grayscale, 19.2 kB per frame).']));
add(B(['Frame packets to the host, e.g. ', c('"CAMF" | u32 seq | u16 w | u16 h | u8 format | data | u16 checksum'), ', resynchronising on the magic like the audio packets.']));
add(B(['Commands from the host as text lines, e.g. ', c('P <pan_deg> <tilt_deg>'), ', ', c('L 0|1'), ' (laser), ', c('?'), ' (status). Reply in a separate packet type so binary frames and replies do not mix.']));
add(B(['Servos: hardware PWM 50 Hz, pulse about 500–2500 µs for 0–180° (calibrate the end points per servo); limit the slew rate; laser off at start-up and whenever no command arrived for a few seconds.']));
add(H2('6.3 Covering the upper hemisphere with two 180° servos'));
add(P('Pan 0° points along the array +x axis; tilt 0° is horizontal along the pan direction, 90° straight up, 180° horizontal in the opposite direction. With azimuth az taken in [0°, 360°) and elevation el in [0°, 90°]:'));
add(B(['az in [0°, 180°): pan = az, tilt = el']));
add(B(['az in [180°, 360°): pan = az − 180°, tilt = 180° − el (the tilt servo leans back over the top)']));
add(P(['The live mode prints azimuth in (−180°, 180°]; convert with ', c('az % 360'), '. Directions below the horizon cannot be reached; clamp el at 0°.']));
add(H2('6.4 Host side to write'));
add(...NUMLIST([
  [c('droneloc live --pointer'), ': send the (smoothed, rate-limited) direction to Pico 2; move only when the change exceeds 2–3°, and preferably between listening windows, because the servos themselves make noise that the array hears. Mount the pan/tilt head at least 50 cm from the sphere (MG995 gears are loud).'],
  ['Viewer/recorder: show the camera image with a centre mark, overlay az/el, record frames and estimates with timestamps.'],
  ['Calibration: point at known loudspeaker positions, fit the pan/tilt zero offsets and the rotation between the array frame and the pan/tilt frame; save to a small JSON file used by --pointer.'],
  ['Error measurement: angular error from the pixel offset of the target to the image centre (degrees per pixel from the lens field of view, measured once with a target at a known angle).'],
]));
add(H2('6.5 Shopping list for this part'));
add(TABLE(['Part', 'Qty', 'Notes'], [
  ['Pan/tilt bracket for standard-size servos (MG995/MG996R), metal', '1', 'Must carry camera + laser'], ['MG995 servo (metal gears)', '2 (+1 spare)', 'Chosen by the user; MG996R is the improved successor'],
  ['Red laser module 650 nm, < 1 mW', '1', 'Indoor tests only'], ['NPN transistor 2N2222 or S8050, 1 kΩ resistor', '1 each', 'Laser switch'],
  ['5 V / 5 A supply and 1000 µF / 16 V capacitor', '1 each', 'Servo and laser power (not 6 V: the laser module is 3–5 V)'],
  ['2 x 4.7 kΩ resistors', '2', 'SCCB pull-ups (many blue OV7670 boards lack them)'],
  ['Second Raspberry Pi Pico (RP2040)', '1', 'Keeps camera and servos off the audio Pico'],
  ['Short female–female Dupont wires', '~25', 'Camera to Pico, under 15 cm'],
  ['Optional: USB webcam', '1', 'Better than OV7670 for outdoor tests; plugs into the Pi directly'],
], [4600, 1600, 3400]));

// ======================================================= 7
add(H1('7. Open items, in order'));
add(...NUMLIST([
  'Bring up Pico 1 with two microphones, then all twelve; verify synchronisation and channel order (section 4.3).',
  'Real-array test with a loudspeaker at known directions (evaluate-array) and in live mode; record the timing on the Pi with experiments/profile_live.py using five references.',
  'Write the Pico 2 firmware and the host side (section 6), test indoors with a loudspeaker and the laser.',
  'If the Pi is too slow with five references: speed up reference cancellation and cross-spectra in the live path only (keep the published path unchanged).',
  'Kalman tracking (direction and range) in live mode.',
  'Later: BNO085 IMU on the Pi (I2C; note the known BNO08x clock-stretching issue on the Raspberry Pi) to convert directions to earth axes.',
  'Merge claude/epic-ride-9fqd2p into main via a pull request when the user asks.',
]));

const doc = new Document({
  creator: 'Husham Saied', title: 'Briefing for Claude Code on the Raspberry Pi',
  styles: { default: { document: { run: { font: F, size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 30, bold: true, color: '1F3864' }, paragraph: { spacing: { before: 320, after: 140 }, outlineLevel: 0, keepNext: true } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 25, bold: true, color: '2E74B5' }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1, keepNext: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 22, bold: true }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2, keepNext: true } }] },
  numbering: { config: [
    { reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } }] },
    { reference: 'bulr', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.RIGHT, style: { paragraph: { indent: { right: 500, hanging: 280 } } } }] },
    ...numRefs.map(r => ({ reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] }))] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1080, bottom: 1080, left: 1150, right: 1150 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: F, size: 18, color: '888888' })] })] }) },
    children: body }] });
Packer.toBuffer(doc).then(buf => { fs.writeFileSync('/home/user/drone/docs/reports/Claude_Code_Briefing.docx', buf); console.log('written'); });
