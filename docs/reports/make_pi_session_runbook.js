// Builds docs/reports/Pi_Session_Runbook_AR.docx (Arabic, right-to-left): node make_pi_session_runbook.js
const fs = require('fs'), path = require('path');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
        ShadingType, BorderStyle, ImageRun, LevelFormat, PageBreak, Footer, PageNumber } = require('docx');
const ROOT = path.resolve(__dirname, '..', '..'), FIG = path.join(ROOT, 'docs', 'figures_ar');
const F = 'Arial';
const runs = (x, base = {}) => (Array.isArray(x) ? x : [x]).map(s => typeof s === 'string'
  ? new TextRun({ text: s, font: F, rightToLeft: true, ...base })
  : new TextRun({ text: s.t, bold: s.b, color: s.c, font: s.code ? 'Consolas' : F, rightToLeft: !s.code, ...base }));
const P = (x, o = {}) => new Paragraph({ bidirectional: true, alignment: AlignmentType.RIGHT, spacing: { after: 120, line: 312 }, ...o, children: runs(x) });
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, bidirectional: true, alignment: AlignmentType.RIGHT, children: runs(t) });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, bidirectional: true, alignment: AlignmentType.RIGHT, children: runs(t) });
const B = x => new Paragraph({ bidirectional: true, alignment: AlignmentType.RIGHT, numbering: { reference: 'bul', level: 0 }, spacing: { after: 60, line: 300 }, children: runs(x) });
let nref = 0; const refs = [];
const NUM = items => { const r = 'n' + nref++; refs.push(r); return items.map(x => new Paragraph({ bidirectional: true, alignment: AlignmentType.RIGHT, numbering: { reference: r, level: 0 }, spacing: { after: 80, line: 300 }, children: runs(x) })); };
const CODE = lines => lines.map((l, k) => new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 0, before: k ? 0 : 40 },
  shading: { type: ShadingType.CLEAR, fill: 'F2F2F2', color: 'auto' }, children: [new TextRun({ text: l || ' ', font: 'Consolas', size: 18 })] }));
const SP = () => new Paragraph({ spacing: { after: 60 }, children: [] });
const b = t => ({ t, b: true }), c = t => ({ t, code: true }), red = t => ({ t, b: true, c: 'C62828' });
const SEND = x => P([{ t: '📤 أرسل لي: ', b: true, c: '1565C0' }, ...(Array.isArray(x) ? x : [x])], { shading: { type: ShadingType.CLEAR, fill: 'E3F2FD', color: 'auto' } });
const WARN = x => P([{ t: '⚠️ ', b: true }, ...(Array.isArray(x) ? x : [x])], { shading: { type: ShadingType.CLEAR, fill: 'FFF3E0', color: 'auto' } });
function IMG(file, wpx, caption) {
  const buf = fs.readFileSync(file), w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  return [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, children: [new ImageRun({ type: 'png', data: buf, transformation: { width: wpx, height: Math.round(wpx * h / w) } })] }),
          P([{ t: caption, b: true, c: '444444' }], { alignment: AlignmentType.CENTER, spacing: { after: 200 } })];
}
const bd = { style: BorderStyle.SINGLE, size: 4, color: 'BBBBBB' };
function TABLE(head, rows, widths) {
  const cell = (x, i, hdr) => new TableCell({ width: { size: widths[i], type: WidthType.DXA }, margins: { top: 50, bottom: 50, left: 90, right: 90 },
    borders: { top: bd, bottom: bd, left: bd, right: bd }, shading: hdr ? { type: ShadingType.CLEAR, fill: 'DDE7F3', color: 'auto' } : undefined,
    children: [(x && x.code) ? new Paragraph({ children: [new TextRun({ text: x.t, font: 'Consolas', size: 18 })] })
      : new Paragraph({ bidirectional: true, alignment: AlignmentType.START, children: runs(x, hdr ? { bold: true, size: 20 } : { size: 20 }) })] });
  return new Table({ width: { size: widths.reduce((a, v) => a + v), type: WidthType.DXA }, columnWidths: widths, visuallyRightToLeft: true,
    rows: [new TableRow({ tableHeader: true, children: head.map((h, i) => cell(h, i, true)) }), ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((x, i) => cell(x, i, false)) }))] });
}
const body = []; const add = (...xs) => xs.forEach(x => Array.isArray(x) ? body.push(...x) : body.push(x));

add(new Paragraph({ alignment: AlignmentType.CENTER, bidirectional: true, spacing: { before: 300, after: 160 }, children: runs(b('دليل جلسة الاختبار على الراسبيري باي'), { size: 40, color: '1F3864' }) }));
add(new Paragraph({ alignment: AlignmentType.CENTER, bidirectional: true, spacing: { after: 300 }, children: runs('مصفوفة الميكروفونات · الرأسان والكاميرتان · البوصلتان — 18 نوفمبر 2026', { size: 22, color: '666666' }) }));
add(P('هذا الدليل يرتّب الاختبار الأول للعتاد الحقيقي خطوة بخطوة. نفّذ المراحل بالترتيب، ولا تنتقل إلى المرحلة التالية قبل نجاح التي قبلها. بعد كل مرحلة أرسل لي ما هو مكتوب في المربع الأزرق، وأنا أحلّل النتائج وأصلح ما يلزم في الكود.'));
add(P([b('تنبيه صريح: '), 'كل البرامج جُرّبت على المحاكاة وعلى حاسوب التطوير فقط، ولم يعمل أي منها على العتاد الحقيقي بعد. من الطبيعي أن تظهر مشكلات في هذه الجلسة الأولى، وسنحلّها معاً.']));
add(TABLE(['المرحلة', 'المحتوى', 'البرنامج'], [
  ['0', 'ملاحظة مهمة عن السيرفوهات (اقرأها أولاً)', '—'],
  ['1', 'تجهيز الباي وتحديث الكود', 'جاهز'],
  ['2', 'البيكو 1 والميكروفونات', [b('جاهز'), ' (pico_mic_array.uf2)']],
  ['3', 'البيكو 2 والسيرفوهات، سيرفو واحد في كل مرة', [b('جاهز الآن'), ' (pico_pointer.uf2)']],
  ['4', 'الكاميرتان', 'لا يحتاج برمجة'],
  ['5', 'البوصلتان (BNO085 وMPU-6050)', [b('جاهز الآن'), ' (python -m droneloc imu)']],
  ['6', 'التشغيل المباشر مع توجيه الرأسين', 'جاهز (بعد المعايرة)'],
], [1300, 5700, 2600]));

// ------------------------------------------------ 0
add(H1('0. ملاحظة مهمة عن السيرفوهات (اقرأها أولاً)'));
add(P([b('ما حدث مع أكواد الاختبار السابقة له تفسير مهم: '), 'السيرفو العادي (موضعي 180°) فيه مقاومة متغيرة ومصدّات داخلية، فلا يستطيع الدوران 360° بلا توقف مهما كان الكود: أقصى ما يفعله أن يذهب إلى طرف مداه ويقف. فإن دار أحد السيرفوهات بلا توقف، فالأرجح أنه ', red('نسخة الدوران المستمر (360°)'), '. يُباع MG995 بنسختين، 180° و360°، وتبدوان متطابقتين من الخارج. أو أن مقاومته الداخلية تالفة.']));
add(P([b('لماذا يهم ذلك؟ '), 'سيرفو الدوران المستمر لا يعرف موقعه: الأمر عنده «سرعة واتجاه» وليس «زاوية»، فلا يصلح لتوجيه الكاميرا. الرأسان يحتاجان ', b('4 سيرفوهات موضعية 180°'), '.']));
add(P([b('أما كود الأردوينو الذي ذكرته '), '(write(0) ثم write(180)): مع السيرفو الموضعي يذهب إلى الطرفين ويقف، وهذا ما رأيته. ومع سيرفو الدوران المستمر يعني «أقصى سرعة في اتجاه» ثم «أقصى سرعة في الاتجاه الآخر» دون توقف.']));
add(H2('اختبار كل سيرفو باليد (دون كهرباء)'));
add(...NUM([['افصل السيرفو تماماً عن أي تغذية.'],
  ['أدر ذراعه (Horn) باليد ببطء شديد.'],
  [b('يقف عند طرفين '), '(حوالي 180° أو أقل بين الطرفين): ', b('موضعي، صالح'), '. لا تضغط عليه عند الطرف.'],
  [b('يدور بلا نهاية: '), red('دوران مستمر، لا يصلح للرأسين'), '. ضع عليه علامة وأبعده.'],
  ['ابحث على ملصق السيرفو عن «360°» أو «Continuous».']]));
add(H2('ميزات الأمان في برنامج البيكو 2 الجديد'));
add(B('عند التشغيل لا يرسل أي نبضات: السيرفو «مرتخٍ» ولا يتحرك أبداً من تلقاء نفسه.'));
add(B([b('مدى محدود جداً افتراضياً: '), '1200 إلى 1800 ميكروثانية (حوالي ±55° حول المنتصف) إلى أن تقيس المدى الحقيقي لكل سيرفو.']));
add(B('حركة بطيئة: لا يقفز السيرفو إلى الزاوية، بل يتحرك إليها تدريجياً.'));
add(B('إذا لم يصله أمر لمدة 5 ثوانٍ يرخي كل السيرفوهات تلقائياً.'));
add(WARN('في أول تجربة: انزع الذراع والكاميرا عن السيرفو، ولا تترك سلكاً يمكن أن يلتف حوله. اجعل يدك قرب مفتاح مزوّد السيرفو، وفي الطرفية يوقف Ctrl+C الحركة ويرخي السيرفو فوراً.'));

// ------------------------------------------------ 1
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('1. تجهيز الباي وتحديث الكود'));
add(P('المستودع عام، وكل الكود الآن في الفرع الرئيسي main (الإصدار 3.0.0). انقل نسخة الباي إليه مرة واحدة بالأمر checkout، وبعدها يكفي git pull:'));
add(CODE(['cd "/home/pi/Desktop/The Dron Project/code"', 'source .venv/bin/activate', 'git fetch origin', 'git checkout -B main origin/main',
  'pip install smbus2', 'sudo apt install -y i2c-tools fswebcam', 'sudo usermod -aG dialout pi']));
add(SP());
add(P([b('تفعيل I2C والمنفذ التسلسلي '), '(للبوصلتين):']));
add(CODE(['sudo raspi-config']));
add(B(['Interface Options ← I2C ← ', b('Yes')]));
add(B(['Interface Options ← Serial Port ← «login shell over serial?» ', b('No'), ' ← «serial port hardware enabled?» ', b('Yes')]));
add(B(['Finish، ثم أعد التشغيل: ', c('sudo reboot')]));
add(P('بعد إعادة التشغيل:'));
add(CODE(['cd "/home/pi/Desktop/The Dron Project/code"', 'source .venv/bin/activate', 'python -m pytest tests']));
add(SEND(['آخر سطر من الاختبارات. المتوقع: ', c('25 passed'), ' (قد يأخذ حوالي 4 دقائق).']));

// ------------------------------------------------ 2
add(H1('2. البيكو 1 والميكروفونات'));
add(...NUM([['لحام أطراف البيكو 1 إن لم تكن ملحومة.'],
  ['تحميل البرنامج: اضغط BOOTSEL واستمر، ووصّل البيكو 1 بمنفذ USB أسود، ثم اترك الزر. يظهر قرص RPI-RP2:'],
]));
add(CODE(['cp hardware/pico_mic_array/pico_mic_array.uf2 /media/pi/RPI-RP2/']));
add(...NUM([['تحقق: الضوء الأخضر يومض مرة كل ثانية، ثم نفّذ:']]));
add(CODE(['lsusb | grep 2e8a', 'ls /dev/ttyACM*']));
add(P(['المتوقع: سطر فيه ', c('2e8a:000a'), '، والمنفذ ', c('/dev/ttyACM0'), '.']));
add(...NUM([['افصل البيكو، ووصّل ', b('ميكروفونين فقط'), ' (القناتان 0 و1 على GP2، وL/R الأول إلى GND والثاني إلى 3V3)، ثم وصّله وافحص:']]));
add(CODE(['python experiments/record_pico.py --check']));
add(P(['المتوقع: القناتان 0 و1 بين ', b('−70 و−55'), ' في الهدوء، وبين ', b('−40 و−20'), ' عند الكلام قربهما. القنوات غير الموصولة حوالي −90. و', c('lost 0 bad 0'), '. أوقفه بـ Ctrl+C.']));
add(...NUM([['أضف زوجاً واحداً في كل مرة (خط SD واحد)، وافحص بعد كل زوج. بعد الاثني عشر سجّل 30 ثانية:']]));
add(CODE(['python experiments/record_pico.py --seconds 30 --out run01.wav']));
add(SEND('ثلاثة أسطر من --check (هدوء، ثم كلام قرب القناة 0، ثم كلام قرب القناة 1)، والأسطر الأخيرة من التسجيل. وإن ظهر خطأ فانسخه كما هو.'));

// ------------------------------------------------ 3
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('3. البيكو 2 والسيرفوهات'));
add(...IMG(path.join(FIG, 'pico2_servo_wiring.png'), 600, 'الشكل 1: توصيل البيكو 2 بالسيرفوهات الأربعة'));
add(H2('3.1 تحميل البرنامج'));
add(P(['اضغط BOOTSEL في ', b('البيكو 2'), '، ووصّله بالمنفذ الأسود الآخر، ثم:']));
add(CODE(['cp hardware/pico_pointer/pico_pointer.uf2 /media/pi/RPI-RP2/', 'python -m droneloc pointer init-cal', 'python -m droneloc pointer status']));
add(P(['المتوقع: خمسة أسطر تبدأ بـ ', c('OK ch0 on=0 ...'), ' حتى ', c('ch3'), '، ثم ', c('OK rate=300 timeout=5'), '. والأمر init-cal ينشئ ملف المعايرة ', c('pointer_cal.json'), ' بالحدود الآمنة 1200–1800.']));
add(H2('3.2 سيرفو واحد فقط: Pan العلوي (القناة 0، GP16)'));
add(...NUM([['انزع الذراع والكاميرا، ووصّل السيرفو: البرتقالي إلى GP16، والأحمر إلى +5V المزوّد، والبني إلى GND المزوّد. ', b('وصّل GND المزوّد بالطرف 23 في البيكو 2'), '.'],
  ['شغّل مزوّد 5V، ثم أرسل المنتصف:']]));
add(CODE(['python -m droneloc pointer servo 0 1500 --hold 5']));
add(P('المتوقع: يتحرك السيرفو إلى المنتصف ويثبت 5 ثوانٍ، ثم يرتخي.'));
add(WARN([b('إن دار السيرفو بلا توقف: '), 'اضغط Ctrl+C وافصل المزوّد فوراً. هذا سيرفو دوران مستمر (القسم 0).']));
add(...NUM([['جرّب الجانبين:']]));
add(CODE(['python -m droneloc pointer servo 0 1300 --hold 3', 'python -m droneloc pointer servo 0 1700 --hold 3']));
add(H2('3.3 قياس المدى الحقيقي لكل سيرفو'));
add(P(['الحد الافتراضي 1200–1800. لتجربة مدى أوسع افتح ملف المعايرة ', c('nano pointer_cal.json'), '، ووسّع حدود السيرفو الذي تختبره، مثلاً ', c('[900, 2100]'), '، واحفظ. ثم جرّب بخطوات صغيرة:']));
add(CODE(['python -m droneloc pointer servo 0 1100 --hold 3', 'python -m droneloc pointer servo 0 1000 --hold 3', '# ... ثم 900، وفي الجهة الأخرى 1900، 2000، 2100']));
add(P([b('أين تتوقف؟ '), 'عندما يتوقف السيرفو عن التحرك، أو يصدر ', b('طنيناً/أزيزاً'), ' عند الطرف: ارجع 50 ميكروثانية. هذا هو حدّه الآمن. لا تتركه يطنّ عند الطرف، فهذا يحرقه.']));
add(P(['سجّل لكل سيرفو: الحد الأدنى، والحد الأقصى، وعدد درجات الدوران تقريباً بين الطرفين. القنوات: ', c('0 = Pan العلوي'), '، ', c('1 = Tilt العلوي'), '، ', c('2 = Pan السفلي'), '، ', c('3 = Tilt السفلي'), '.']));
add(TABLE(['القناة', 'السيرفو', 'الحد الأدنى (µs)', 'الحد الأقصى (µs)', 'المدى (درجات تقريباً)'], [
  ['0', 'Pan العلوي (GP16)', '', '', ''], ['1', 'Tilt العلوي (GP17)', '', '', ''],
  ['2', 'Pan السفلي (GP18)', '', '', ''], ['3', 'Tilt السفلي (GP19)', '', '', ''],
], [1100, 2600, 1950, 1950, 2000]));
add(SP());
add(H2('3.4 بعد تركيب الرأسين'));
add(P('ضع الحدود المقاسة في pointer_cal.json، وركّب الكاميرتين، ثم وجّه الرأسين إلى اتجاهات بسيطة ولاحظ أين تتجه كل كاميرا:'));
add(CODE(['python -m droneloc pointer point 0 30 --hold 5      # للأمام، ارتفاع 30° (الرأس العلوي)', 'python -m droneloc pointer point 90 30 --hold 5     # إلى اليسار (محور y)', 'python -m droneloc pointer point 0 -30 --hold 5     # للأمام، أسفل الأفق (الرأس السفلي)']));
add(P('الاتجاهات بالنسبة للكرة: x للأمام، وy لليسار، وz للأعلى. من الطبيعي ألا تتجه الكاميرا بالضبط في البداية؛ ملاحظاتك تحدد قيم المعايرة (إزاحة الصفر واتجاه الدوران).'));
add(SEND('جدول المدى للسيرفوهات الأربعة، ونتيجة pointer status، وأين اتجهت كل كاميرا في الأوامر الثلاثة (مثلاً: «اتجهت يميناً بدل اليسار»).'));

// ------------------------------------------------ 4
add(H1('4. الكاميرتان'));
add(P('وصّل الكاميرتين بالمنفذين الأزرقين (USB 3)، ثم:'));
add(CODE(['ls /dev/v4l/by-id/', 'fswebcam -d /dev/video0 -r 1280x720 --no-banner cam_a.jpg', 'fswebcam -d /dev/video2 -r 1280x720 --no-banner cam_b.jpg']));
add(P(['افتح الصورتين للتأكد. إن ظهر خطأ في ', c('/dev/video2'), '، استخدم الأسماء التي ظهرت في ', c('/dev/v4l/by-id/'), ' بدلاً منه (كل كاميرا تظهر غالباً باسمين، والصالح للصورة عادة هو المنتهي بـ ', c('index0'), ').']));
add(SEND('نتيجة ls /dev/v4l/by-id/، وهل ظهرت الصورتان.'));

// ------------------------------------------------ 5
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('5. البوصلتان'));
add(H2('5.1 لماذا هاتان القطعتان من بين ما عندك؟'));
add(TABLE(['القطعة', 'ماذا تقيس', 'القرار'], [
  [b('BNO085'), 'تسارع + جيروسكوب + بوصلة، ويدمجها داخلياً فيعطي الاتجاه جاهزاً', [b('نعم: على الكرة'), ' — الجهاز الأهم، وبعيد عن السيرفوهات']],
  [b('MPU-6050 (GY-521)'), 'تسارع + جيروسكوب (6 محاور)', [b('نعم: على قاعدة الرأسين'), ' — ميل دقيق من الجاذبية، والجيروسكوب يكشف الاهتزاز']],
  ['HW-290', 'غالباً لوحة GY-87 (فيها MPU-6050 + بوصلة HMC5883L + ضغط)', 'بديل احتياطي للـ GY-521 (نفس الشريحة)'],
  ['ADXL345 (GY-291)', 'تسارع فقط', 'احتياطي: يعطي الميل فقط، دون جيروسكوب'],
  ['HMC5883L (GY-273) / MLX90393', 'بوصلة مغناطيسية فقط', 'لا نحتاجها: قرب السيرفوهات تتشوش، ولا تقيس الميل'],
], [2500, 3800, 3300]));
add(SP());
add(P([b('لماذا لا نحتاج بوصلة مغناطيسية على الرأسين؟ '), 'مغناطيس محركات MG995 وتيارها يشوّشان أي بوصلة قريبة. لذلك يُضبط اتجاه الرأسين الأفقي (yaw) ', b('مرة واحدة بالكاميرا'), ' عند المعايرة، وهذا أدق. بعدها يراقب MPU-6050 أي ميل أو اهتزاز للحامل. لا حاجة لشراء أي قطعة جديدة.']));
add(...IMG(path.join(FIG, 'imu_wiring.png'), 600, 'الشكل 2: توصيل البوصلتين بالـ Raspberry Pi'));
add(H2('5.2 التوصيل والاختبار'));
add(TABLE(['القطعة', 'طرف القطعة', 'طرف الباي'], [
  ['BNO085', 'VIN', 'الطرف 1 (3V3)'], ['BNO085', 'GND', 'الطرف 6 (GND)'], ['BNO085', 'SDA (خرج RVC)', 'الطرف 10 (GPIO15 RXD)'], ['BNO085', 'P0', '3V3 (مع VIN)'],
  ['MPU-6050', 'VCC', 'الطرف 17 (3V3)'], ['MPU-6050', 'GND', 'الطرف 9 (GND)'], ['MPU-6050', 'SDA', 'الطرف 3 (GPIO2 SDA)'], ['MPU-6050', 'SCL', 'الطرف 5 (GPIO3 SCL)'],
  ['MPU-6050', 'AD0', 'GND (العنوان 0x68)'],
], [2600, 3200, 3800]));
add(SP());
add(P([b('تحقق من نمط BNO085: '), 'في دليل Adafruit للوحة 4754 (قسم UART-RVC): خرج البيانات في هذا النمط هو الطرف المكتوب عليه SDA، وP0 يوصل إلى 3V3. تأكد من ذلك في لوحتك قبل التوصيل.']));
add(CODE(['i2cdetect -y 1                # يجب أن يظهر 68', 'ls -l /dev/serial0             # يجب أن يكون موجوداً', 'python -m droneloc imu']));
add(P(['المتوقع: سطر كل نصف ثانية مثل ', c('sphere yaw 123.45 pitch 0.80 roll -1.20 | heads roll 0.40 pitch 1.10 gyro 0.3 deg/s'), '. أمِل الكرة بيدك فيتغيّر pitch/roll للكرة، والمس قاعدة الرأسين فتظهر عبارة ', c('<- moving!'), '.']));
add(P([b('إن ظهر «sphere: no data»: '), 'تأكد من توصيل SDA إلى الطرف 10، وP0 إلى 3V3، وأن المنفذ التسلسلي مفعّل (المرحلة 1). ولتشغيل بوصلة واحدة فقط: ', c("python -m droneloc imu --bno ''"), ' (MPU فقط) أو ', c('--mpu-bus -1'), ' (BNO فقط).']));
add(SEND('بضعة أسطر من python -m droneloc imu: والكرة ساكنة، ثم أثناء إمالتها، ثم عند لمس قاعدة الرأسين. ونتيجة i2cdetect.'));

// ------------------------------------------------ 6
add(H1('6. التشغيل المباشر مع توجيه الرأسين'));
add(P('بعد نجاح المراحل السابقة ومعايرة الرأسين: ضع سمّاعة تشغّل صوت درون على بعد حوالي 3 أمتار من الكرة، ثم:'));
add(CODE(['python -m droneloc live --refs 6,7,8,9,10 --cal 3 --bpf 105,200 --steering sphere --hop 0.5 --pointer --range 3 --log live.csv']));
add(P(['خلال أول 3 ثوانٍ (المعايرة) أبقِ السمّاعة صامتة. الخيار ', c('--range 3'), ' يصحّح فرق موقع الرأسين عن الكرة (يُدخَل موقعهما بالمتر في pointer_cal.json، في الحقلين upper_pos_m وlower_pos_m). عند الإيقاف بـ Ctrl+C ترتخي السيرفوهات تلقائياً.']));
add(SEND('آخر 10 أسطر من التشغيل، وهل كانت الكاميرا تتجه نحو السمّاعة.'));

add(H1('ملاحظات عامة'));
add(B(['إن ثبّتّ نظام 64-بت وClaude Code على الباي، أعطه ملف ', c('docs/reports/Claude_Code_Briefing.md'), ' ليعرف كل التفاصيل.']));
add(B(['منافذ USB: البيكوان في المنفذين الأسودين، والكاميرتان في الأزرقين. البرنامج يميّز البيكوين بالاسم.']));
add(B(['لا تغذِّ السيرفوهات من الباي أو البيكو أبداً، ولكل رأس مزوّده.']));

const doc = new Document({ creator: 'Husham Saied', title: 'دليل جلسة الاختبار على الراسبيري باي',
  styles: { default: { document: { run: { font: F, size: 22 } } }, paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 30, bold: true, color: '1F3864' }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0, keepNext: true } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 25, bold: true, color: '2E74B5' }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1, keepNext: true } }] },
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.RIGHT, style: { paragraph: { indent: { right: 500, hanging: 280 } } } }] },
    ...refs.map(r => ({ reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.RIGHT, style: { paragraph: { indent: { right: 500, hanging: 320 } } } }] }))] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1080, bottom: 1080, left: 1150, right: 1150 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: F, size: 18, color: '888888' })] })] }) },
    children: body }] });
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(path.join(ROOT, 'docs', 'reports', 'Pi_Session_Runbook_AR.docx'), buf); console.log('written'); });
