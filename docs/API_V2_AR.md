> **ملاحظة إصدار 2.2:** بعض الأقسام أدناه تخص الإصدار السابق، مثل الديون، مطابقة الفواتير، العجز والفائض وحساب النقد المعدود. مسارات API وصفحات هذه المزايا متوقفة في 2.2، ولا تُنشأ قيود ديون جديدة. الاعتماد الجديد يتم من سجل الورديات بقرار إداري دون جرد نقدي. راجع `docs/UPDATE_V2_2_AR.md` و`README_AR.md` للأوامر المعتمدة حاليًا.

# واجهة API

الأساس `/api`. في التطوير توجد وثيقة OpenAPI على `/api/openapi.json`، ونسخة ثابتة ضمن `docs/openapi-v2.json`. الإنتاج لا يعرض Swagger أو OpenAPI تلقائيًا.

| العملية | الدور |
|---|---|
| POST /auth/login وGET /auth/me وPOST /auth/logout | الحساب المصادق عليه |
| POST /attachments وPOST /shifts | الموظف أو المدير للإدخال؛ رد التسليم لا يعيد البيانات أو الأرقام |
| GET /shifts وGET /shifts/{id} | المدير فقط؛ ويمكن تحديد version للقراءة التاريخية |
| PUT /shifts/{id} | المدير؛ expected_version وreason إلزاميان، وينشئ نسخة جديدة |
| GET /invoices وPOST /invoices/{id}/match | المدير؛ مراجعة السطور وربط الدين السابق |
| POST /shifts/{id}/preview وPOST /shifts/{id}/reconcile | المدير؛ إعادة حساب في الخادم والجرد الصريح |
| GET /reports و/reports/months و/reports/export.pdf و/reports/export.csv | المدير؛ day أو month أو from_date/to_date، وemployee_id اختياري |
| GET /shifts/{id}/export.pdf وGET /attachments/{id} | المدير فقط |
| GET /customers و/customers/{id} | المدير؛ كشف الحساب |
| POST /customers/opening-debts | المدير؛ رصيد افتتاحي مستقل |
| POST /customers/debts/{id}/cancel-opening | المدير؛ عكس افتتاحي غير مسدد بسبب موثق |
| GET/POST /users وPUT/DELETE /users/{id} | المدير؛ الحذف تعطيل وصول وليس حذف سجلات |
| GET/PUT /settings وGET /audit | المدير |
| GET /notifications وPOST /notifications/{id}/retry وPOST /notifications/monthly | المدير |
| POST /integrations/outbox/claim | رمز n8n؛ حجز مهمة واحدة |
| POST /integrations/deliveries/{id}/result | رمز n8n مع lease_token |
| POST /integrations/monthly-reports | رمز n8n؛ الشهر السابق افتراضيًا |
| GET /integrations/events/{id}/report.pdf | رمز n8n؛ لقطة تقرير الحدث |

كتابات المستخدم تتطلب Cookie الجلسة و`X-CSRF-Token` وقيمة `Idempotency-Key` عشوائية 16 إلى 64 محرفًا. رأس CSRF يؤخذ من Cookie `bin_doul_csrf`؛ Session Cookie غير مقروءة من JavaScript. طلب المعاينة لا يكتب بيانات لكنه يحتاج المصادقة وCSRF.

أرسل المبالغ كنصوص مثل `"1000.50"`. لا ترسل مجموع مشتريات أو ديون، أو فرق مطابقة محسوبًا من المتصفح. عدد الصنف integer فقط. يرفض المخطط الحقول غير المعروفة.

رفع المرفق الاختياري طلب POST إلى `/attachments` بمحتوى الملف نفسه، وليس multipart؛ يرسل `X-Filename` باسم ملف مرمز URL، وContent-Type مناسبًا، وCSRF ومفتاح الطلب. الرد يضم `id` لاستخدامه في سطر مشتريات أو دين أو تحويل بنكي، ولا يتيح للموظف تنزيل المرفق بعد تسليمه. الخادم يتحقق من توقيع النوع والحجم وسلامة الصور وملكية المرفق.

رقم فاتورة الشراء والدين وتحويل فاتورة الوردية اختياري. اسم المورد/المدين، القيمة، وصف المشتريات والدين، وإجمالي فاتورة الدين، ورقم المرجع البنكي واجبات حسب نوع العملية. يسمح بإدخال أكثر من وردية لنفس الموظف في التاريخ نفسه بمرجع سند إيداع مختلف ومفتاح `Idempotency-Key` جديد لكل تسليم مستقل. لا يُربط سطران برقم فاتورة فارغ تلقائيًا.

قراءة الملفات والتقارير والورديات تحمى في الخادم؛ إخفاء قوائم الواجهة ليس آلية الصلاحيات الوحيدة. جميع الاستجابات تحمل `Cache-Control: no-store`.

أخطاء القواعد عربية: 401 للدخول، 403 للصلاحية/CSRF، 409 للتكرار أو التعارض أو النسخة القديمة، 422 للبيانات والقواعد المالية، 413 لحجم المرفق، و503 لعدم تأكيد معاملة قاعدة البيانات. عند خطأ شبكة أعد المحاولة بالجسم والمفتاح نفسيهما.
