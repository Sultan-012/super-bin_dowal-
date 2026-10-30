# API إصدار 2.4

الأساس /api. المخطط الكامل الحالي `openapi-v2_4.json`. /api/docs و/api/openapi.json متاحان في التطوير فقط، ويتوقفان في الإنتاج.

| المسار | الصلاحية |
|---|---|
| POST /auth/login، GET /auth/me، POST /auth/logout | الدخول والجلسة الحالية |
| POST /shifts، POST /attachments | الموظف أو المدير؛ رد التسليم مجرد إقرار دون بيانات الوردية |
| GET /shifts، GET /shifts/{id}، GET /shifts/{id}/export.pdf | المدير فقط؛ version لنسخة قديمة للقراءة |
| PUT /shifts/{id} | المدير؛ سبب وexpected_version؛ يضيف نسخة ولا يستبدل الأصل |
| POST /shifts/{id}/confirm | المدير؛ confirmed=true وexpected_version؛ اعتماد إداري |
| GET /reports، /reports/export.pdf، /reports/export.csv | المدير؛ day أو month أو from_date/to_date، وemployee_id |
| GET /reports/analytics | المدير؛ month بالصيغة YYYY-MM وmonths=1..24 (6 افتراضيًا) وemployee_id اختياري |
| GET /attachments/{id} | المدير فقط |
| GET/POST /users، PUT/DELETE /users/{id} | المدير؛ DELETE تعطيل وحفظ السجلات |
| GET/PUT /settings، GET /audit | المدير |
| GET /notifications، POST /notifications/{id}/retry، POST /notifications/monthly | المدير |
| POST /integrations/outbox/claim | رمز n8n المحدود؛ مفتاح طلب فريد |
| POST /integrations/deliveries/{id}/result | رمز الخدمة وlease_token |
| POST /integrations/monthly-reports | رمز الخدمة؛ شهر مكتمل فقط |
| GET /integrations/events/{id}/report.pdf | رمز الخدمة؛ لقطة التقرير المخزنة |

كتابة المستخدم تحتاج Cookie الجلسة HttpOnly وX-CSRF-Token من bin_doul_csrf وIdempotency-Key عشوائي 16..64 محرفًا. المفتاح نفسه مع محتوى مختلف يرفض 409. رمز الخدمة لا يمنح صلاحية إدارة المستخدمين أو تعديل الوردية. لا تخزن Tokens في LocalStorage.

المبالغ نصوص مثل "10000.50"؛ الحقول غير المعروفة مرفوضة، والقيم المحتسبة يعيد الخادم حسابها. النص ذو NUL أو Unicode غير صالح يرفض 422، وكذلك الأسماء والمراجع المكونة من محارف مخفية فقط. الجسم JSON محدود 512KiB أثناء البث أيضًا، والمرفق 5MiB. الملف يرسل بمحتواه المباشر وContent-Type وX-Filename مشفر URL، وليس multipart. تتحقق ملكيته ونوعه الفعلي وامتداده، وتمنع ملفات PDF ذات JavaScript/تشغيل تلقائي/ملفات مضمّنة أو بنية خطرة.

مسارات /customers و/invoices و/reconcile و/preview السابقة غير مفعلة في تحديث 2.2 وما بعده، ولا تستخدمها للتكامل الجديد.
