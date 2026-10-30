# نظام إدارة المبيعات ومطابقة الصندوق

**Daily Sales & Cash Reconciliation System — الإصدار 1.0**

تطبيق لمتجر واحد وصندوق واحد: ملخص المبيعات اليومية، البيع الآجل والتحصيل، المشتريات والحركات النقدية، الجرد والإغلاق، وكشوف العملاء والتقارير. الواجهة عربية وتدعم RTL والهواتف والطباعة وتصدير CSV بالعربية. جميع الأرقام تأتي من API وقاعدة البيانات، ولا يستخدم التطبيق LocalStorage لتخزين البيانات أو المصادقة.

## ما تتضمنه الحزمة

- `frontend/`: React 19 + TypeScript + Vite، ومكونات الواجهة الفعلية.
- `backend/app/`: FastAPI وSQLAlchemy والقواعد المالية والمصادقة والصلاحيات.
- `backend/migrations/`: ترحيلات Alembic ثابتة الإصدار، بما فيها حماية سجل التدقيق ولقطات الإغلاق من التعديل والحذف.
- `backend/tests/`: اختبارات الحسابات وAPI والحفظ والصلاحيات والتزامن وسلامة المعاملات.
- `docs/sqlserver-schema.sql`: مخطط SQL Server المولّد من الترحيلات، للمراجعة أو التهيئة البديلة.
- `docs/FINANCIAL_RULES_AR.md`: مصادر الأرقام والمعادلات وسلوك التصحيح والإغلاق.
- `docs/DATABASE_AR.md`: بنية البيانات والأقفال والصلاحيات والنسخ والاستعادة.
- `docs/TEST_RESULTS_AR.md`: ما نُفّذ فعليًا وحدود التحقق.
- `sample-data/acceptance-example.json`: بيانات مثال اختيارية منفصلة تمامًا عن بيانات التشغيل.

لا تتضمن الحزمة قاعدة تشغيل مملوءة أو حسابًا بكلمة مرور افتراضية أو ملف `.env` حقيقيًا. لا يوجد تكامل مع جهاز الشبكة، أو مخزون، أو نظام فواتير أو محاسبة عامة.

## 1. متطلبات Windows

1. Windows 10/11 بنظام x64.
2. Python **3.12 x64**. اختر Add Python to PATH أثناء التثبيت.
3. Node.js **22.12 أو أحدث من سلسلة LTS**؛ بُني المشروع في بيئة Node 24.22.1.
4. SQL Server، مثل SQL Server 2022 Express، أو مثيل SQL Server قائم مع رخصة مناسبة لاستخدامك.
5. Microsoft ODBC Driver **18 for SQL Server x64**.
6. SQL Server Management Studio (SSMS) لإنشاء القاعدة وإدارة النسخ الاحتياطية.

روابط المصادر الرسمية:

- [Python لويندوز](https://www.python.org/downloads/windows/)
- [Node.js](https://nodejs.org/en/download)
- [تنزيلات SQL Server](https://www.microsoft.com/en-us/sql-server/sql-server-downloads)
- [ODBC Driver 18](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- [متطلبات Vite](https://vite.dev/guide/)

## 2. فك الحزمة وإنشاء قاعدة SQL Server

فك الملفات مثلًا في `C:\Projects\daily-sales`. افتح SSMS واتصل بالمثيل، ثم نفّذ مرة واحدة:

```sql
CREATE DATABASE DailySales;
GO
```

للاتصال بمثيل SQL Server عبر منفذ TCP، فعّل TCP/IP في SQL Server Configuration Manager ثم أعد تشغيل خدمة SQL Server عند الحاجة. تحقق من اسم المثيل والمنفذ الفعلي. لا يلزم فتح منفذ SQL Server للإنترنت.

يمكن استخدام Windows Authentication محليًا، أو إنشاء Login مخصص من واجهة SSMS بكلمة مرور تختارها هناك. لا تنسخ كلمة المرور إلى ملفات المشروع أو سجل الأوامر. لإنشاء المخطط والترحيلات يحتاج حساب التهيئة إلى صلاحية إنشاء الجداول والفهارس والـTriggers. بعد التهيئة استخدم حساب تشغيل محدود الصلاحيات؛ مثال الصلاحيات في `docs/runtime-permissions.sql`.

## 3. إعداد البيئة والاتصال

افتح PowerShell داخل مجلد المشروع:

```powershell
py -3.12 -m venv .venv
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

افتح `.env` بمحرر محلي. للتشغيل المحلي عبر HTTP فقط اضبط:

```dotenv
APP_ENV=development
COOKIE_SECURE=false
ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000,http://localhost:5173,http://127.0.0.1:5173
DEFAULT_CURRENCY=SAR
DEFAULT_TIMEZONE=Asia/Riyadh
```

لتوليد سر خاص بهذه النسخة شغّل:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

انسخ الناتج إلى `IDEMPOTENCY_SECRET` في `.env`. احتفظ بالسر مع إعدادات التشغيل الآمنة؛ لا تضمه إلى Git أو التقارير. يستخدم لحماية بصمات الطلبات التي تحتوي كلمات مرور؛ الجلسات نفسها تستخدم رموزًا عشوائية منفصلة.

استخدم **واحدًا** من أمثلة الاتصال التالية، بعد تعديل الأسماء محليًا:

Windows Authentication، مثيل افتراضي:

```dotenv
DATABASE_URL=mssql+pyodbc://@localhost/DailySales?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes
```

Windows Authentication، مثيل Express باسم SQLEXPRESS:

```dotenv
DATABASE_URL=mssql+pyodbc://@localhost%5CSQLEXPRESS/DailySales?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes
```

SQL Authentication عبر المنفذ 1433، **قالب فقط دون بيانات اعتماد**:

```dotenv
DATABASE_URL=mssql+pyodbc://USER:PASSWORD@localhost:1433/DailySales?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

استبدل USER وPASSWORD من إعداداتك. يجب ترميز المحارف الخاصة في اسم المستخدم وكلمة المرور بصيغة URL؛ مثل `@` إلى `%40` و`#` إلى `%23` و`%` إلى `%25`. لا تُدخل رابط الاتصال الحقيقي في أمر يُحفظ في السجل. `TrustServerCertificate=yes` مخصص للتطوير المحلي مع شهادة محلية؛ بيئة التشغيل الفعلية تستخدم شهادة موثوقة و`Encrypt=yes&TrustServerCertificate=no`.

العملة والمنطقة الزمنية الافتراضيتان تطبقان عند إنشاء أول مدير. يمكن تعديلهما من الإعدادات وفق القيود المالية الموضحة أدناه. يمكنك استخدام `YER` و`Asia/Aden` إذا كانا مناسبين لمتجرك.

## 4. تطبيق الترحيلات وإنشاء أول مدير

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.cli create-admin
Set-Location ..
```

يسأل الأمر عن اسم مستخدم لاتيني، واسم كامل، وكلمة مرور لا تقل عن 12 حرفًا وتأكيدها، دون إظهارها. يرفض إنشاء مدير أول جديد إذا وُجد مستخدم بالفعل. لا يضيف أي بيانات مبيعات. أنشئ المستخدمين التاليين من شاشة الإعدادات بحساب المدير.

إذا أردت مراجعة SQL قبل التنفيذ:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head --sql > ..\schema-review.sql
Set-Location ..
```

الطريقة الموصى بها هي `alembic upgrade head`. ملف SQL المرفق بديل للقاعدة الفارغة فقط، ويحتوي جدول إصدار Alembic؛ لا تطبق الملف والترحيلات الأولية معًا على قاعدة أُنشئت بالفعل. لا تستخدم `downgrade` أو إسقاط الجداول على قاعدة التشغيل.

## 5. بناء الواجهة وتشغيل التطبيق

```powershell
Set-Location frontend
npm ci
npm run build
Set-Location ..
.\.venv\Scripts\python.exe scripts\serve.py --host 127.0.0.1 --port 8000
```

افتح [http://127.0.0.1:8000](http://127.0.0.1:8000) وسجّل الدخول بالمدير الذي أنشأته. يقدم FastAPI ملفات React وAPI من المصدر نفسه. لا تحتاج الإنترنت لتشغيل الواجهة بعد تثبيت الحزم وبنائها.

لاختبار الاتصال: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health). تتوفر وثائق API في `/api/docs` أثناء التطوير فقط. أمثلة بيانات الاعتماد لا تُعرض في صفحة الدخول.

أوقف الخادم بـ Ctrl+C ثم شغله بالطريقة نفسها؛ تبقى العمليات في SQL Server. حذف مجلد `frontend/dist` أو إعادة بناء React لا يحذف البيانات.

### تطوير الواجهة مع التحديث المباشر

في نافذة أولى، من `backend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

وفي نافذة ثانية من `frontend`:

```powershell
npm run dev
```

افتح `http://localhost:5173`. يمرر Vite طلبات `/api` إلى FastAPI. لا تستخدم خادم Vite للتشغيل الفعلي.

## 6. الاستخدام اليومي

1. افتح جلسة بتاريخ العمل. لأول جلسة أدخل رصيد الافتتاح، وفي الجلسات التالية يُرحّل النقد الفعلي المعتمد تلقائيًا.
2. سجّل إجمالي المبيعات قبل المرتجعات، ومبيعات الشبكة التي يشملها ذلك الإجمالي، ثم احفظ.
3. أضف البيع الآجل كسجلات ديون مرتبطة بالعملاء؛ تُجمع قيمتها آليًا ولا تدخلها ثانية في حقل آخر.
4. سجّل كل تحصيل منفصلًا مع طريقة الدفع. استخدم أرصدة افتتاحية للديون السابقة للنظام، بصلاحية مدير.
5. سجّل كل فاتورة مشتريات وحدد إن دُفعت من الصندوق، وأدخل المصروفات والسحوبات والإيداعات والمرتجعات منفصلة.
6. أدخل الجرد الفعلي. يُمكن حفظه دون إغلاق، لكنه يصبح جردًا سابقًا إذا أضفت عمليات بعده.
7. اختر مراجعة وإغلاق اليوم، وراجع المتوقع والفعلي والفرق المحسوب من الخادم، ثم اعتمد. الملاحظة إلزامية عند وجود عجز أو فائض.

لا يمكن فتح يوم جديد قبل إغلاق السابق. لا تتغير العمليات المغلقة. التصحيح يتم بإعادة الفتح الموثقة لآخر جلسة فقط، أو إلغاء سجل داخل جلسة مفتوحة مع الاحتفاظ بأصله وسببه. لا تدعم النسخة تعديل تاريخ يوم قديم بعد بدء يوم لاحق أو عكس عمليات جلسة مغلقة داخل يوم آخر؛ هذه القيود تمنع كسر ترحيل النقد.

## 7. الاختبارات

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run build
Set-Location ..
```

اختبارات API الافتراضية تستخدم ملفات SQLite مؤقتة داخل مجلد الاختبارات، مع ترحيلات حقيقية وقيود ومفاتيح خارجية. لا تتصل بقاعدة التشغيل ولا تختزن الأموال في ذاكرة التطبيق. **SQLite مسموح فقط في `APP_ENV=test` وليس بديلًا عن SQL Server في التشغيل أو التطوير.** نجاح هذه الاختبارات لا يثبت سلوك أقفال SQL Server؛ يوجد اختبار اتصال فعلي منفصل.

### اختبار SQL Server الحقيقي الاختياري

أنشئ قاعدة **جديدة وفارغة تمامًا** باسم مثل `DailySales_acceptance_test`، ثم اضبط `TEST_SQLSERVER_URL` في متغير بيئة محلي، دون إضافته إلى Git. مثال Windows Authentication دون كلمة مرور:

```powershell
$env:TEST_SQLSERVER_URL = 'mssql+pyodbc://@localhost/DailySales_acceptance_test?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes'
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q -m sqlserver
Set-Location ..
Remove-Item Env:TEST_SQLSERVER_URL
```

الاختبار يرفض أي اسم لا ينتهي بـ `_acceptance_test` وأي قاعدة تحتوي جداول. يطبق الترحيلات، ويسجل المثال المالي، ويختبر التكرار المتزامن والحفظ وإعادة التشغيل والترحيل، ويترك بياناته في قاعدة الاختبار. لإعادة الاختبار استخدم قاعدة اختبار فارغة أخرى. لا يستخدم الاختبار `DROP DATABASE` ولا يحذف قاعدة قائمة تلقائيًا.

## 8. بيانات المثال المنفصلة

لا تُحمّل أمثلة عند فتح التطبيق. لإنشاء بيئة تدريب اختيارية:

1. أنشئ قاعدة منفصلة مثل `DailySalesSample`.
2. شغّل الترحيلات وأنشئ مديرًا فيها باستعمال متغير اتصال تلك القاعدة.
3. من `backend` شغّل:

```powershell
..\.venv\Scripts\python.exe -m app.sample_data --confirm-sample-database
```

يرفض المحمّل أي قاعدة لا يحتوي اسمها على `Sample` أو تحتوي مسبقًا عملاء أو جلسات. البيانات بتاريخ `2026-10-01`؛ اختر ذلك التاريخ لعرض المثال. الرصيد المتوقع **1700.00** ولا يوجد جرد معتمد افتراضيًا. أعد اتصال التشغيل إلى قاعدة `DailySales` قبل إدخال العمليات الحقيقية.

## 9. التشغيل الفعلي والأمان

- اضبط `APP_ENV=production` و`COOKIE_SECURE=true`، وأضف عنوان HTTPS الفعلي إلى `ALLOWED_ORIGINS`.
- استخدم HTTPS عبر وكيل محلي مُعدّ مثل IIS، أو شغّل Uvicorn بشهادة ومفتاح محليين موثوقين. لا تُضمّن الشهادات الخاصة في المستودع.
- مثال Uvicorn من `backend`، بعد إعداد الشهادة والمفتاح لديك:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8443 --ssl-certfile C:\Secure\store.crt --ssl-keyfile C:\Secure\store.key
```

- جرى تجزئة كلمات المرور بـArgon2id. ملفات Cookie للمصادقة HttpOnly وSameSite=Strict، مع حماية CSRF وفحص Origin. رموز الجلسات مخزنة كتجزئات فقط وتلغى عند التعطيل أو إعادة تعيين كلمة المرور.
- الصلاحيات مفروضة في API. التقارير وإدارة المستخدمين والإلغاء وإعادة الفتح للمدير. حساب الموظف يدخل معاملات الجلسة المفتوحة ويعرض لوحة يوم واحد.
- جميع عمليات الكتابة متسلسلة بقفل قاعدة بيانات لصندوق المتجر الواحد، وليس بقفل ذاكرة داخل عملية Python؛ يمكن تشغيل أكثر من عامل دون تجاوز القواعد.
- كل عملية مالية تتطلب `Idempotency-Key`، وتُعاد الاستجابة السابقة عند إعادة نفس الطلب، ويُرفض استخدام المفتاح لطلب مختلف. الواجهة تمنع الضغط المتكرر وتحتفظ بمفتاح المحاولة عند فشل الاتصال.
- لا توجد واجهة حذف دائم للمعاملات المالية. تُحفظ الأصول والعمليات الملغاة في التقارير التفصيلية وسجل التدقيق.
- انسخ SQL Server احتياطيًا بانتظام واختبر الاستعادة، وفق `docs/DATABASE_AR.md`.

لم يُنشر هذا المشروع خارجيًا. يجب إتمام اختبار SQL Server الحقيقي على جهازك والتحقق من النسخ الاحتياطي وإعداد HTTPS قبل الاعتماد التشغيلي.

## 10. حل أخطاء الإعداد الشائعة

| العَرَض | الإجراء |
|---|---|
| `IM002` أو عدم العثور على Driver | ثبّت ODBC Driver 18 x64، وتحقق من مطابقته لـPython x64. |
| `Login failed` | راجع حساب Windows الحالي أو بيانات SQL Login وصلاحياته على القاعدة. |
| تعذر الوصول للخادم | تحقق من اسم المثيل، TCP/IP، المنفذ الفعلي وخدمة SQL Server. |
| خطأ شهادة محلي | استخدم شهادة موثوقة، أو `TrustServerCertificate=yes` في التطوير المحلي فقط. |
| لا تظل مسجلًا على HTTP محلي | اضبط `APP_ENV=development` و`COOKIE_SECURE=false` وأعد تشغيل الخادم. |
| «مصدر الطلب غير مسموح» | أضف المصدر الدقيق، مثل `http://localhost:8000`، إلى `ALLOWED_ORIGINS` وأعد تشغيل الخادم. |
| «تغيّرت بيانات الجلسة» | حدّث الصفحة وراجع المبالغ؛ سجّل مستخدم آخر حركة بعد فتح النموذج. |
| لا تظهر الواجهة | نفّذ `npm ci` ثم `npm run build` داخل `frontend` وأعد تشغيل الخادم. |
| الجداول غير موجودة | تحقق من قاعدة الاتصال ثم نفّذ `alembic upgrade head`. |
| مفتاح العملية مستخدم لطلب مختلف | افتح النموذج من جديد بعد مراجعة السجل؛ لا تكرر العملية عشوائيًا. |

لا تعرض التطبيق أو قاعدة البيانات مباشرة على الإنترنت أثناء الإعداد. لا ترسل ملف `.env` أو نسخة قاعدة البيانات إلى الآخرين ضمن تقارير الأخطاء.
