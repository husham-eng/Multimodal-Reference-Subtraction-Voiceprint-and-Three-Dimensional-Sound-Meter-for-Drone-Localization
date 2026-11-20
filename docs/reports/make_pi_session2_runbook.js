// Builds docs/reports/Pi_Session2_Runbook_AR.docx (Arabic, right-to-left): node make_pi_session2_runbook.js
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

const UP = '/dev/v4l/by-id/usb-046d_Brio_100_2629ZB52EJT8-video-index0', LO = '/dev/v4l/by-id/usb-046d_Brio_100_2629ZBT2TAK8-video-index0';

add(new Paragraph({ alignment: AlignmentType.CENTER, bidirectional: true, spacing: { before: 300, after: 160 }, children: runs(b('دليل جلسة الاختبار الثانية على الراسبيري باي'), { size: 40, color: '1F3864' }) }));
add(new Paragraph({ alignment: AlignmentType.CENTER, bidirectional: true, spacing: { after: 300 }, children: runs('كهرباء الرأسين · معايرة الاتجاه بالكاميرا · التشغيل المباشر — 21 نوفمبر 2026', { size: 22, color: '666666' }) }));
add(P('في جلسة أمس (20 نوفمبر) فحصنا كل قطعة وحدها، وكلها تعمل. هدف اليوم أن تعمل القطع معاً: الرأسان يتحركان بكهرباء ثابتة، ونعرف بالكاميرا أين يتجه كل رأس، ثم نجرّب التشغيل المباشر مع سمّاعة تشغّل صوت درون.'));
add(P('نفّذ المراحل بالترتيب، ولا تنتقل إلى المرحلة التالية قبل نجاح التي قبلها. بعد كل مرحلة أرسل لي ما هو مكتوب في المربع الأزرق.'));

add(H2('نتائج جلسة أمس'));
add(TABLE(['القطعة', 'الحالة', 'ملاحظة'], [
  ['البيكو 1 والميكروفونات الستة', b('✅ تعمل'), 'بعد إصلاح توقيت القراءة في برنامج البيكو. الهدوء بين −58 و−55'],
  ['البيكو 2 والسيرفوهات الأربعة', b('✅ تعمل'), 'كلها موضعية 180°. المدى من 600 إلى 2400 µs لكل سيرفو'],
  ['الكاميرتان', b('✅ تعملان'), 'cam_a (ZB52EJT8) على الرأس العلوي، وcam_b (ZBT2TAK8) على الرأس السفلي'],
  ['BNO085 (الكرة)', b('✅ تعمل'), 'P0 موصول بطرف 3Vo في اللوحة نفسها'],
  ['MPU-6050 (قاعدة الرأسين)', b('✅ تعمل'), 'AD0 موصول بالأرضي'],
  ['أسلاك الكهرباء داخل الرأسين', red('❌ لا توصل'), 'اختبرنا كل سيرفو بأسلاك قصيرة مباشرة'],
  ['الباور بانك', red('❌ لا يصلح'), 'ينطفئ وحده. شاحن الحائط يكفي لسيرفو واحد فقط'],
], [3000, 1700, 4900]));

add(H2('خطة اليوم'));
add(TABLE(['المرحلة', 'المحتوى', 'الوقت التقريبي'], [
  ['0', 'فتح الطرفية وتحديث الكود', '5 دقائق'],
  ['1', 'كهرباء السيرفوهات وأسلاك الرأسين', '30–60 دقيقة'],
  ['2', 'فحص شامل لكل القطع', '5 دقائق'],
  ['3', 'معايرة اتجاه الرأسين بالكاميرا', '30–45 دقيقة'],
  ['4', 'التشغيل المباشر مع سمّاعة', '20 دقيقة'],
  ['5', 'الميكروفونات المرجعية (إن بقي وقت)', '30 دقيقة'],
], [1300, 5800, 2500]));

// ------------------------------------------------ 0
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('0. فتح الطرفية وتحديث الكود'));
add(P(['افتح الطرفية بالضغط على Ctrl + Alt + T. ثم ', b('اكتب'), ' هذا السطر بيدك، لا تلصقه. بدونه تظهر رموز غريبة مثل ', c('^[[200~'), ' عند اللصق عبر TeamViewer:']));
add(CODE(["bind 'set enable-bracketed-paste off'"]));
add(P('ثم الصق هذه الأوامر:'));
add(CODE(['cd "/home/pi/Desktop/The Dron Project/code" && source .venv/bin/activate', 'git fetch origin && git reset --hard origin/claude/epic-ride-9fqd2p']));
add(P(['تأكد أن السطر يبدأ بـ ', c('(.venv)'), '. إذا ظهر الخطأ ', c('No module named droneloc'), '، فمعناه أنك لست في مجلد المشروع، أو أن البيئة غير مفعّلة. أعد السطر الأول.']));
add(WARN([b('لا تحذف الملف pointer_cal.json. '), 'فيه حدود السيرفوهات التي قسناها أمس. الأمر ', c('git reset'), ' لا يحذفه.']));

// ------------------------------------------------ 1
add(H1('1. كهرباء السيرفوهات وأسلاك الرأسين'));
add(H2('1.1 مصدر الكهرباء'));
add(P(['كل سيرفو MG995 يسحب حتى ', b('2 أمبير'), ' عند بدء الحركة. السيرفوهات الأربعة معاً تحتاج مزوّداً بهذه المواصفات:']));
add(B([b('الجهد: '), '5 إلى 6 فولت.']));
add(B([b('التيار: '), '5 أمبير على الأقل، مثل محوّل 5V 5A أو 6V 5A، أو مزوّداً لكل رأس بتيار 3 أمبير.']));
add(B([b('لا تستخدم: '), 'الباور بانك (ينطفئ وحده)، ولا طرف 5V في الباي أو في البيكو.']));
add(WARN([b('الأرضي المشترك ضروري: '), 'سالب المزوّد (−) يجب أن يكون موصولاً بأحد أطراف GND في البيكو 2، مثل الطرف 3 أو 23. بدونه يبقى السيرفو مرتخياً ولا يفهم الإشارة، وهذا ما حدث أمس.']));

add(H2('1.2 أسلاك الرأسين'));
add(P('أسلاك الكهرباء داخل الرأسين لم توصل الكهرباء أمس. لكل سيرفو ثلاثة أسلاك:'));
add(TABLE(['سلك السيرفو', 'يذهب إلى', 'ملاحظة'], [
  [b('البرتقالي (الإشارة)'), 'طرفه في البيكو 2', 'القناة 0 ← الطرف 21، والقناة 1 ← 22، والقناة 2 ← 24، والقناة 3 ← 25'],
  [b('الأحمر (+)'), 'موجب المزوّد (+)', 'الأسلاك الحمراء الأربعة معاً'],
  [b('البني (−)'), 'سالب المزوّد (−)', 'الأسلاك البنية الأربعة معاً، وسلك منها إلى GND البيكو 2'],
], [2600, 2600, 4400]));
add(SP());
add(P([b('افحص كل وصلة باليد: '), 'رؤوس الأسلاك (Dupont) ترتخي بسهولة. أمس انقطع بسببها سلك WS في البيكو 1، وتوقف سيرفو القناة 2 بعد أول حركة. إذا كان رأس السلك واسعاً، فاستبدل السلك كله. وثبّت الأسلاك بشريط لاصق أو برباط، حتى لا تشدّها حركة الرأس.']));
add(P([b('الطرف 23 في البيكو 2 أرضي: '), 'لا تضع فيه سلك إشارة. أطراف السيرفوهات هي 21 و22 و24 و25.']));

add(H2('1.3 اختبار كل سيرفو على أسلاك الرأس'));
add(P('شغّل المزوّد، ثم اختبر كل قناة وحدها بمسح قصير حول المنتصف:'));
add(CODE(['python -m droneloc pointer sweep 0 1200 1800 100 --hold 1', 'python -m droneloc pointer sweep 1 1200 1800 100 --hold 1',
  'python -m droneloc pointer sweep 2 1200 1800 100 --hold 1', 'python -m droneloc pointer sweep 3 1200 1800 100 --hold 1']));
add(P(['أول سطر يجب أن يُظهر ', c('lim=600..2400'), '. إذا ظهر ', c('lim=1200..1800'), '، فقد ضاع ملف المعايرة. أعد الحدود بالأمر ', c('python -m droneloc pointer limits CH 600 2400'), ' لكل قناة.']));
add(H2('1.4 السيرفوهات الأربعة معاً'));
add(P('أرسل الرأسين إلى المنتصف في وقت واحد، وراقب هل يرتجف أي سيرفو أو يتوقف:'));
add(CODE(['python -m droneloc pointer point 0 30 --hold 10']));
add(P('ثم اختبر الرأس السفلي:'));
add(CODE(['python -m droneloc pointer point 0 -30 --hold 10']));
add(WARN([b('إذا ارتجفت السيرفوهات أو أعاد البيكو تشغيل نفسه: '), 'المزوّد ضعيف، أو أن أسلاك الكهرباء رفيعة جداً. اضغط Ctrl + C فوراً.']));
add(SEND('هل تحركت السيرفوهات الأربعة على أسلاك الرأسين؟ ونوع المزوّد الذي استخدمته (الجهد والتيار).'));

// ------------------------------------------------ 2
add(H1('2. فحص شامل لكل القطع'));
add(P('برنامج الفحص يمر على كل القطع دون أن يحرّك أي سيرفو:'));
add(CODE(['bash experiments/check_hardware.sh']));
add(TABLE(['القسم', 'المتوقع'], [
  ['System', [c('throttled=0x0'), '. إذا ظهرت قيمة أخرى، فشاحن الباي ضعيف: استخدم الشاحن الأصلي 5V 3A']],
  ['1. USB', ['بيكوان باسميهما (DroneLoc Mic Array وDroneLoc Pointer)، و', c('/dev/ttyACM0'), ' و', c('/dev/ttyACM1')]],
  ['2. الميكروفونات', 'القنوات 0 إلى 5 بين −60 و−50 تقريباً، والقنوات 6 إلى 11 عند −180'],
  ['3. السيرفوهات', [c('on=0'), ' للقنوات الأربع، و', c('lim=600..2400')]],
  ['4. الكاميرتان', 'صورتان cam_*.jpg'],
  ['5. البوصلتان', ['العنوان ', c('68'), '، و', c('/dev/serial0'), '، وأسطر فيها قيم sphere وheads']],
], [2400, 7200]));
add(SP());
add(SEND('الملف hw_check.txt كاملاً.'));

// ------------------------------------------------ 3
add(H1('3. معايرة اتجاه الرأسين بالكاميرا'));
add(P('البرنامج يحسب زوايا السيرفوهات من اتجاه الصوت. لكنه يحتاج أن يعرف أربعة أشياء عن كل رأس:'));
add(B([b('زاوية الصفر للدوران الأفقي: '), 'عند أي زاوية تنظر الكاميرا إلى الأمام (+x).']));
add(B([b('زاوية الصفر للميل: '), 'عند أي زاوية تكون الكاميرا أفقية.']));
add(B([b('اتجاه الدوران: '), 'هل يدور السيرفو في الاتجاه المتوقع أم بعكسه. أمس رأينا أن الرأس السفلي معكوس كالمرآة.']));
add(B([b('موقع الرأس: '), 'بُعده عن مركز الكرة بالمتر.']));
add(H2('3.1 اتجاهات الكرة'));
add(P([b('x للأمام '), '(جهة الميكروفون +x، وهو ميكروفون القناة 0)، و', b('y لليسار'), '، و', b('z للأعلى'), '. ضع ورقة مكتوب عليها «أمام» على الحائط في جهة +x، وورقة «يسار» على الحائط في جهة +y.']));
add(H2('3.2 وجّه الرأس وصوّر بالكاميرا'));
add(P('كل أمر يوجّه الرأس 15 ثانية. بعد 6 ثوانٍ تلتقط الكاميرا صورة مما تراه:'));
add(CODE([`python -m droneloc pointer point 0 20 --hold 15 & sleep 6; fswebcam -d ${UP} -r 1280x720 -S 30 --no-banner up_front.jpg`]));
add(CODE([`python -m droneloc pointer point 90 20 --hold 15 & sleep 6; fswebcam -d ${UP} -r 1280x720 -S 30 --no-banner up_left.jpg`]));
add(CODE([`python -m droneloc pointer point 0 -20 --hold 15 & sleep 6; fswebcam -d ${LO} -r 1280x720 -S 30 --no-banner lo_front.jpg`]));
add(CODE([`python -m droneloc pointer point 90 -20 --hold 15 & sleep 6; fswebcam -d ${LO} -r 1280x720 -S 30 --no-banner lo_left.jpg`]));
add(TABLE(['الأمر', 'الرأس', 'المتوقع'], [
  [c('point 0 20'), 'العلوي', 'ورقة «أمام»، فوق الأفق بقليل'],
  [c('point 90 20'), 'العلوي', 'ورقة «يسار»، فوق الأفق بقليل'],
  [c('point 0 -20'), 'السفلي', 'ورقة «أمام»، تحت الأفق بقليل'],
  [c('point 90 -20'), 'السفلي', 'ورقة «يسار»، تحت الأفق بقليل'],
], [2600, 1600, 5400]));
add(SP());
add(P('من الطبيعي ألا تتجه الكاميرا بالضبط في البداية. ملاحظاتك هي التي تحدد قيم المعايرة.'));
add(H2('3.3 قِس موقع كل رأس'));
add(P(['بشريط القياس، قِس بُعد ', b('مركز كل كاميرا'), ' عن ', b('مركز الكرة'), ' بالسنتيمتر في الاتجاهات الثلاثة: كم سنتيمتراً للأمام (x)، ولليسار (y)، وللأعلى (z). القيمة سالبة إذا كان الرأس للخلف أو لليمين أو للأسفل.']));
add(SEND(['الصور الأربع، وأين اتجهت كل كاميرا (مثلاً «يميناً بدل اليسار» أو «أعلى من الأفق كثيراً»)، وقياسات موقع الرأسين. وأرسل أيضاً ناتج ', c('python -m droneloc imu --seconds 5'), ' والجهاز في مكانه النهائي، ليكون نقطة الصفر للبوصلتين.']));
add(P('بعدها أحسب قيم المعايرة وأرسل لك أمراً واحداً يحفظها، ثم نعيد الصور الأربع للتأكد.'));

// ------------------------------------------------ 4
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('4. التشغيل المباشر مع سمّاعة'));
add(P(['ضع سمّاعة تشغّل صوت درون على بعد ', b('حوالي 3 أمتار'), ' من الكرة، وفي جهة ', b('خالية'), ' أمام أحد الرأسين، أي بعيداً عن الهيكل والأسلاك. ثم:']));
add(CODE(['python -m droneloc live --bpf 105,200 --steering sphere --hop 0.5 --pointer --range 3 --log live.csv']));
add(P(['الميكروفونات المرجعية (القنوات 6 إلى 11) غير موصولة بعد، لذلك لا يحتوي الأمر على ', c('--refs'), '. الخيار ', c('--range 3'), ' يصحّح فرق موقع الرأسين عن الكرة. عند الإيقاف بـ Ctrl + C ترتخي السيرفوهات تلقائياً.']));
add(...NUM([
  ['شغّل صوت الدرون وانتظر 10 ثوانٍ: يجب أن يتجه أحد الرأسين نحو السمّاعة.'],
  ['انقل السمّاعة ببطء إلى جهة أخرى: يجب أن يتبعها الرأس.'],
  ['ارفع السمّاعة فوق الكرة، ثم أنزلها تحتها: يجب أن ينتقل التوجيه بين الرأس العلوي والرأس السفلي.'],
]));
add(SEND('آخر 10 أسطر من التشغيل، والملف live.csv، وهل كانت الكاميرا تتجه نحو السمّاعة في كل خطوة.'));

// ------------------------------------------------ 5
add(H1('5. الميكروفونات المرجعية (إن بقي وقت)'));
add(P('تُوصل بالطريقة نفسها التي وُصلت بها ميكروفونات الكرة: SCK إلى GP8، وWS إلى GP9، وVDD إلى 3V3، وGND إلى GND.'));
add(TABLE(['القناة', 'الدور', 'سلك SD', 'L/R'], [
  ['6', 'مرجع الدوّار 1', 'GP5 (الطرف 7)', 'GND'], ['7', 'مرجع الدوّار 2', 'GP5 (الطرف 7)', '3V3'],
  ['8', 'مرجع الدوّار 3', 'GP6 (الطرف 9)', 'GND'], ['9', 'مرجع الدوّار 4', 'GP6 (الطرف 9)', '3V3'],
  ['10', 'مرجع المحطة', 'GP7 (الطرف 10)', 'GND'], ['11', 'احتياطي', 'GP7 (الطرف 10)', '3V3'],
], [1300, 3000, 3000, 2300]));
add(SP());
add(P('أضف زوجاً واحداً في كل مرة، ثم افحص. أمس تبيّن أن الصوت يظهر بوضوح فوق 100 هرتز:'));
add(CODE(['timeout 10 python experiments/record_pico.py --check']));
add(SEND('الأسطر بعد كل زوج: في الهدوء، ثم عند التصفيق.'));

// ------------------------------------------------ appendix
add(new Paragraph({ children: [new PageBreak()] }));
add(H1('ملحق: دروس جلسة أمس'));
add(TABLE(['ما يحدث', 'السبب', 'الحل'], [
  [['رموز ', c('^[[200~'), ' عند اللصق'], 'اللصق عبر TeamViewer', [c("bind 'set enable-bracketed-paste off'"), ' بيدك في كل طرفية جديدة']],
  [c('No module named droneloc'), 'البيئة غير مفعّلة', [c('cd ".../code" && source .venv/bin/activate')]],
  ['قراءة غريبة في كل الميكروفونات', 'سلك مرتخٍ (WS أمس)', 'افحص الأسلاك. فصل SCK أو WS يجب أن يجعل القنوات −180'],
  ['السيرفو مرتخٍ ولا يتحرك', 'لا أرضي مشترك، أو المزوّد منطفئ', 'سالب المزوّد إلى GND البيكو 2. لا تستخدم الباور بانك'],
  ['السيرفو تحرك مرة ثم توقف', 'سلك مرتخٍ أو الشاحن فصل', 'ثبّت الأسلاك. افصل الشاحن ثم أعد توصيله'],
  ['BNO085: 0 bytes received', 'السلك على BT بدل P0', 'P0 هو الثاني في الصف. أعد تشغيل البوصلة بعد أي تغيير'],
  ['MPU-6050 يظهر ويختفي', 'AD0 غير موصول', 'AD0 إلى GND'],
  ['صورة الكاميرا مظلمة', 'أول إطار قبل ضبط السطوع', [c('fswebcam -S 30')]],
  [['البيكو لا يظهر كـ ', c('RPI-RP2')], 'لم يدخل وضع التحميل', 'افصل USB، واضغط BOOTSEL، ثم وصّل USB واترك الزر'],
], [2900, 2900, 3800]));

add(H2('خريطة الأطراف'));
add(TABLE(['القطعة', 'الطرف', 'إلى'], [
  ['البيكو 1', 'SD للأزواج x وy وz', 'GP2 وGP3 وGP4 (الأطراف 4 و5 و6)'],
  ['البيكو 1', 'SCK / WS', 'GP8 / GP9 (الطرفان 11 و12)'],
  ['البيكو 1', 'VDD / GND', 'الطرف 36 / الطرف 38'],
  ['البيكو 2', 'إشارات القنوات 0 إلى 3', 'الأطراف 21 و22 و24 و25 (والطرف 23 أرضي)'],
  ['BNO085', 'VIN / GND / SDA', 'الباي: الطرف 1 / الطرف 6 / الطرف 10'],
  ['BNO085', 'P0', '3Vo في اللوحة نفسها (BT غير موصول)'],
  ['MPU-6050', 'VCC / GND / SDA / SCL / AD0', 'الباي: 17 / 9 / 3 / 5 / GND آخر (14 أو 20)'],
], [2000, 3400, 4200]));

const doc = new Document({ creator: 'Husham Saied', title: 'دليل جلسة الاختبار الثانية على الراسبيري باي',
  styles: { default: { document: { run: { font: F, size: 22 } } }, paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 30, bold: true, color: '1F3864' }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0, keepNext: true } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 25, bold: true, color: '2E74B5' }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1, keepNext: true } }] },
  numbering: { config: [{ reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.RIGHT, style: { paragraph: { indent: { right: 500, hanging: 280 } } } }] },
    ...refs.map(r => ({ reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.RIGHT, style: { paragraph: { indent: { right: 500, hanging: 320 } } } }] }))] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1080, bottom: 1080, left: 1150, right: 1150 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: F, size: 18, color: '888888' })] })] }) },
    children: body }] });
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(path.join(ROOT, 'docs', 'reports', 'Pi_Session2_Runbook_AR.docx'), buf); console.log('written'); });
