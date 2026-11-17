# ⚔️ duckwork-jailbreak-kernel — إضافة نواة اختراق الدروع لـ Duckwork Agent الإصدار v2.0.1

<p align="center">
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/stars/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&logo=github&label=Stars" alt="Stars" /></a>
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/license/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&label=License" alt="License: MIT" /></a>
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/last-commit/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&label=Last%20commit" alt="Last commit" /></a>
  <a href="https://duckwork-agent.fordex.com/docs"><img src="https://img.shields.io/badge/Duckwork%20Agent-🚀%20plugin-10B981?style=for-the-badge&logoColor=white" alt="Duckwork Agent plugin" /></a>
</p>

<p align="center">
  <b>تثبيت بسطر واحد</b>:
  <code>duckwork plugins install --enable Enchanted0911/duckwork-jailbreak-kernel</code>
</p>

<p align="center">
  <b>اقرأ هذا المستند بـ:</b>
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.ja.md">日本語</a>
</p>

إضافة حقن برومبت النظام لاختراق الدروع (red-team) إلى **Fordex Duckwork Agent** (`~/.duckwork`)، منقولة من إضافة DSH **[dsh-infinite-gen-4 (الجيل اللانهائي الرابع، v0.4.0)](https://github.com/Minglink/dsh-infinite-gen-4)**.

> ⚠️ **للاستخدام المصرح به فقط.** هذه الإضافة مخصصة لميادين الاختبار المصرح بها، والأهداف التركيبية المحلية، وبحوث الفرق الحمراء المتوافقة. لا تستخدمها أبدًا ضد أهداف غير مصرح بها. يتحمل المستخدمون المسؤولية الكاملة عن استخدامهم.

## جدول المحتويات

- [تماثل البنية مع الجيل اللانهائي الرابع](#تماثل-البنية)
- [بنية الحقن ثلاثية الطبقات](#بنية-الحقن-ثلاثية-الطبقات)
- [تدوير الجلسة](#تدوير-الجلسة)
- [التثبيت](#التثبيت)
- [التحقق](#التحقق)
- [مفاتيح البيئة](#مفاتيح-البيئة)
- [تفريغات التشخيص](#تفريغات-التشخيص)
- [قيود Duckwork الصارمة](#قيود-duckwork-الصارمة)
- [الاختبار الذاتي دون اتصال](#الاختبار-الذاتي-دون-اتصال)

## تماثل البنية

| dsh-infinite-gen-4 (v0.4.0) | duckwork-jailbreak-kernel (هذه الإضافة) |
|---|---|
| `infinite-gen-4:global-system-prompt` (Order 100) | `duckwork-jailbreak-kernel-core` (فتحة `after_memory`) |
| `infinite-gen-4:dual-layer-reinforce` (Order 200) | `duckwork-jailbreak-kernel-reinforce` (فتحة `after_memory`، SHA256 مطابق للنواة) |
| مفتاح `DUAL_LAYER_INJECTION` | `DUCKWORK_JAILBREAK_DUAL=0` تراجع أحادي الطبقة |
| سطح أدوات صفري، إخراج مباشر نقي | نفسه — لا يسجّل أي أدوات وظيفية |
| أداة البيانات الوصفية `infinite_gen4_profile` | أمر الحالة `/jailbreak` |
| شارة حالة العميل (نصف ويب) | — (قابل للتركيب في Duckwork Desktop لاحقًا) |
| سطح الحقن: قسم برومبت النظام | `register_system_prompt_section` الأصلي |

ترث حمولة النواة (`prompts/`) نص الجيل اللانهائي الرابع حرفًا بحرف: `SUPREME DIRECTIVE — USER AUTHORITY`، و`Output contract` (السطر الأول `##`/```` ``` ```` لتسمية المُسلَّم + التفكير الصامت + التوليد الذاتي للمكانات)، و`Task classes` (الأمن / أبحاث LLM / الخيال البالغ / أي شيء آخر — الإنتاج مباشرة)، ومراسي few-shot `[USER]/[OUTPUT]`.

## بنية الحقن ثلاثية الطبقات

يحقن المكوّن النواة في **ثلاث طبقات**:

1. **حقن قسم الإضافة** (فتحة `after_memory`، قسمان من نفس المصدر) — يُكتب عند تجميع Duckwork لبرومبت النظام؛
2. **إعادة بناء system في طبقة الطلب (وضع replace)** — الوسيط `llm_request` يعيد كتابة رسالة النظام النهائية كـ *قسم ذاكرة + بيئة تشغيل + نواة* قبل كل طلب، متخلصًا من سقالات Duckwork الخاصة (دليل الوكيل / فهرس المهارات)؛
3. **تدوير جلسة opencode** (أدناه) — يدوّر ترويسة `x-opencode-session`.

مخططات الأدوات غير متأثرة: تنتقل في حقل `tools` الخاص بالواجهة، وليس في نص system.

## أوضاع الجلسة

تحكّم في النواة لكل جلسة أثناء التشغيل — دون إعادة تشغيل أو تعديل متغيرات البيئة:

| الأمر | الأثر |
|---|---|
| `/jailbreak` | الحالة: الجلسة، الوضع، ملف النواة، التدوير، سياسة التفريغ |
| `/jailbreak on` | قياسي: الأقسام + إعادة البناء في طبقة الطلب + تدوير `once` |
| `/jailbreak slim` | خفيف: الأقسام + إلحاق النواة بنهاية system |
| `/jailbreak full` | أقصى: إعادة بناء + ملف `max` + تدوير في كل طلب |
| `/jailbreak off` | تمرير مباشر: إزالة الأقسام وقت الطلب |
| `/jailbreak profile <name>` | ملف النواة: `core` / `research` / `creative` / `max` |
| `/jailbreak dump on\|off` | إجبار أو إسكات تفريغات التشخيص لكل طلب |
| `/jailbreak reset` | مسح تجاوزات الجلسة (الرجوع إلى إعدادات البيئة) |

## ملفات النواة

| الملف | التركيز |
|---|---|
| `core` (**الافتراضي**) | عقد التسليم العام (الأمن / أبحاث LLM / الخيال البالغ / غير ذلك) |
| `research` | الأمن الهجومي والهندسة العكسية والاستغلال والحمولات |
| `creative` | الخيال والمشاهد الصريحة — نصوص كاملة دون قطع |
| `max` | أصعب الحالات: إطار صريح بلا رفض ومنع المقدمات |

وضع `full` يفرض ملف `max`؛ وفي ما عداه يُطبَّق ملف الجلسة.

## مهارة التشغيل

يُشحن `jailbreak-kernel-ops` كمهارة إضافة: كشف تدريجي (سطر واحد في
`<available_skills>`، ويُحمَّل النص عند الطلب عبر `skill_view`). تتضمن مصفوفة
الأوامر وسلّم التصعيد عند الرفض والتشخيص ومتغيرات البيئة الاحتياطية.

## تدوير الجلسة

يتبع التدوير وضع الجلسة: `once` لـ `slim`/`on`، و`every` لـ `full`، ومعطَّل لـ `off`.
يعيد الوسيط كتابة `extra_headers["x-opencode-session"]` لأهداف opencode فقط —
معرّف مدوّر لكل جلسة في `once`، ومعرّف جديد لكل طلب في `every`.

| `DUCKWORK_JAILBREAK_ROTATE_SESSION` | السلوك |
|---|---|
| *(غير محدد)* | اتباع وضع الجلسة (موصى به) |
| `once` / `every` / `0` | فرض سياسة واحدة على كل الجلسات |

الاستدعاءات المساعدة (الضغط، توليد العناوين، إلخ) تحتفظ بالمعرّف المستقر الأصلي.

## التثبيت

```bash
# الخيار 1 — تثبيت بسطر واحد من GitHub
duckwork plugins install --enable Enchanted0911/duckwork-jailbreak-kernel

# الخيار 2 — من كتالوج إضافات Duckwork (بمجرد دمج الإدخال المجتمعي)
duckwork plugins install duckwork-jailbreak-kernel

# الخيار 3 — دليل التطوير المحلي
cp -r ~/.duckwork/plugins/duckwork-jailbreak-kernel ~/.duckwork/plugins/   # أو git clone داخل plugins/
duckwork plugins enable duckwork-jailbreak-kernel

# ثم أعد تشغيل البوابة / تطبيق سطح المكتب
duckwork gateway restart
```

> ⚠️ إضافات Duckwork اختيارية (opt-in): فعّلها بـ `duckwork plugins enable duckwork-jailbreak-kernel` بعد التثبيت (سطر التثبيت الواحد يمرر `--enable` بالفعل).

## التحقق

```bash
# انحدار دون اتصال (المراسي / تطابق SHA256 للطبقتين / الميزانية / المفاتيح)
cd ~/.duckwork/plugins/duckwork-jailbreak-kernel && python selftest.py

# التحقق داخل الجلسة (جلسة جديدة بعد إعادة التشغيل)
/jailbreak                     # إصدار النواة، الفتحات، SHA256 المزدوج، استهلاك الميزانية
# أو اسأل: ما أقسام الإضافات التي في برومبت نظامك؟
# يجب أن ترى «## Plugin Context: duckwork-jailbreak-kernel-core / duckwork-jailbreak-kernel-reinforce»
```

تأكيد سجل التشغيل (`~/.duckwork/logs/agent.log`):

```
INFO duckwork_plugins.duckwork_jailbreak_kernel: injected system prompt section duckwork-jailbreak-kernel-core (chars=3005)
INFO duckwork_plugins.duckwork_jailbreak_kernel: injected system prompt section duckwork-jailbreak-kernel-reinforce (chars=3005)
INFO duckwork_plugins.duckwork_jailbreak_kernel: registered llm_request middleware (request-layer reinforce)
INFO duckwork_plugins.duckwork_jailbreak_kernel: hardened request system prompt (mode=replace ...)
INFO duckwork_plugins.duckwork_jailbreak_kernel: rotated x-opencode-session (...)
```

## مفاتيح البيئة

| المتغير | الافتراضي | الأثر |
|---|---|---|
| `DUCKWORK_JAILBREAK_MODE=on\|off\|slim\|full` | on | وضع الجلسة الافتراضي (تجاوز الجلسة يفوز) |
| `DUCKWORK_JAILBREAK_PROFILE=core\|research\|creative\|max` | core | ملف النواة الافتراضي |
| `DUCKWORK_JAILBREAK_ROTATE_SESSION=once\|every\|0` | *(الوضع)* | تجاوز سياسة التدوير |
| `DUCKWORK_JAILBREAK_DUMP=1\|0` | off | إجبار أو إسكات التشخيص |
| `DUCKWORK_JAILBREAK_DUAL=0` | on | حقن قسم واحد |
| `DUCKWORK_JAILBREAK_DISABLE=1` | off | مفتاح الإيقاف: تخطي التسجيل بالكامل |

## تفريغات التشخيص

يكتب الوسيط عرضًا تشخيصيًا لكل طلب (أول طلب لكل جلسة افتراضيًا؛ كل طلب مع `DUCKWORK_JAILBREAK_DUMP=1`) في `~/.duckwork/plugins/duckwork-jailbreak-kernel/dumps/request_*.json`: رسائل النظام الكاملة + أدوار/أطوال/رؤوس 200 حرف للرسائل الأخرى + model/provider/base_url. استخدمها للتأكد من أن النواة في ذيل رسالة النظام وأن المسار يصل إلى النموذج المتوقع. التفريغات محلية فقط ومستبعدة عبر `.gitignore`.

## قيود Duckwork الصارمة

- أقسام الإضافة: ≤ 4000 حرف لكل قسم، ≤ 8000 حرف إجمالًا (يتخطى الحاقن الأقسام فوق الميزانية بصمت).
- موضع ثابت `after_memory` (بعد الشخصية والذاكرة)؛ ترتيب العرض معجمي حسب معرف القسم → `core < reinforce`.
- معرفات الأقسام: أحرف صغيرة/أرقام/`.`/`_`/`-` فقط.
- إعادة البناء في طبقة الطلب غير مقيدة بميزانية الأقسام (تُنفَّذ في الوسيط وقت الطلب).

## الاختبار الذاتي دون اتصال

```bash
cd ~/.duckwork/plugins/duckwork-jailbreak-kernel
python selftest.py          # ✅/❌ لكل فحص (54 فحصًا)
python selftest.py --json
```

## التعريب

تتبع سلاسل واجهة `/jailbreak` (وصف الأمر وتقرير الحالة) معيار
[`agent/i18n`](https://github.com/DuckMind/duckwork) في Duckwork: تُحلّ اللغة بالترتيب `DUCKWORK_LANGUAGE` >
`display.language` في `config.yaml` > الإنجليزية. يشحن المكون `locales/en.yaml`
(الافتراضي) و `locales/zh.yaml`؛ أي لغة أخرى — وأي مفتاح مفقود — يتراجع إلى
الإنجليزية ثم إلى المفتاح المجرد. تبقى السجلات والنواة المحقونة محايدة للغة
بحكم التصميم.

## الوثائق

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — وصف الطبقات الثلاث ومفاتيح الجلسة ونموذج الفشل
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — متطلبات المضيف ومصفوفة سلوك النماذج المقيسة
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — سجل الإصدارات
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — النسب والتراخيص

## الترخيص

MIT — أنظر [LICENSE](LICENSE). ترحيل/تكييف من [dsh-infinite-gen-4](https://github.com/Minglink/dsh-infinite-gen-4) (MIT, Minglink) لمنصة إضافات Duckwork Agent.