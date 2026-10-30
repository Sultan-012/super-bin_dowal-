# قائمة حذف مقترحة - بانتظار موافقتك

عدد الملفات: 74. الحجم الإجمالي التقريبي: 0.96 MiB. لم ينفذ حذفها.

النطاق هو هذه الملفات المحددة من نسخة الإصدار الجديدة فقط. الأرشيف الأصلي دون تغيير. لا يتضمن الطلب قاعدة البيانات أو جداولها أو سجلات الديون والجرد القديمة، ولا .env، ولا المرفقات التشغيلية أو النسخ الاحتياطية. تبقى كل ترحيلات PostgreSQL الأربعة والكود الحالي واختباراته وملفات n8n.

فحص الاستيراد: frontend/src/main.tsx يستورد shift/App؛ الخادم النشط هو shift_app.main:create_app؛ أوامر التشغيل الحالية لا تستعمل backend/app أو scripts/serve.py أو scripts/serve.mjs. الاختبارات الثلاثة القديمة تستهدف مسارات تقاعدت في 2.2 ولا تدخل مجموعة اختبار النسخة الحالية.

بعد موافقتك تحذف القائمة في نسخة جديدة منفصلة، ثم يعاد فحص البناء والاختبارات والمراجع المتأثرة ويصدر ZIP منظف. لا يعني هذا إذن حذف ملفات على جهازك أو أي بيانات تشغيل. البصمات والأحجام لكل ملف في deletion-proposal.json.

## ملفات خادم SQL Server الأول غير المستخدم

25 ملفات:

- `backend/alembic.ini`
- `backend/app/__init__.py`
- `backend/app/cli.py`
- `backend/app/common.py`
- `backend/app/config.py`
- `backend/app/db.py`
- `backend/app/finance.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/sample_data.py`
- `backend/app/schemas.py`
- `backend/app/security.py`
- `backend/app/services.py`
- `backend/migrations/env.py`
- `backend/migrations/script.py.mako`
- `backend/migrations/versions/0001_initial_schema.py`
- `backend/migrations/versions/0002_append_only.py`
- `backend/requirements-legacy.txt`
- `backend/requirements-lock.txt`
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/test_additional_integrity.py`
- `backend/tests/test_endpoints.py`
- `backend/tests/test_finance.py`
- `backend/tests/test_sqlserver.py`

## واجهة الإصدار الأول غير المستوردة في المدخل الحالي

14 ملفات:

- `frontend/src/Customers.tsx`
- `frontend/src/Daily.tsx`
- `frontend/src/Dashboard.tsx`
- `frontend/src/History.tsx`
- `frontend/src/Movements.tsx`
- `frontend/src/Reports.tsx`
- `frontend/src/Settings.tsx`
- `frontend/src/api.ts`
- `frontend/src/components.tsx`
- `frontend/src/context.ts`
- `frontend/src/dialogs.tsx`
- `frontend/src/legacy-main.tsx`
- `frontend/src/styles.css`
- `frontend/src/types.ts`

## اختبارات ومسارات تشغيل قديمة متوقفة

6 ملفات:

- `backend/shift_tests/test_active_chain.py`
- `backend/shift_tests/test_opening_reversal.py`
- `backend/shift_tests/test_snapshot.py`
- `scripts/prepare-v2_2-tests.py`
- `scripts/serve.mjs`
- `scripts/serve.py`

## توثيق ومخططات ونتائج وأمثلة تاريخية استبدلتها وثائق 2.4

27 ملفات:

- `INSTALL_UI_v2_3_AR.txt`
- `MANIFEST_SHA256.txt`
- `docs/API_V2_AR.md`
- `docs/DATABASE_V2_AR.md`
- `docs/FINANCIAL_RULES_V2_AR.md`
- `docs/LEGACY_V1_DATABASE_AR.md`
- `docs/LEGACY_V1_FINANCIAL_RULES_AR.md`
- `docs/LEGACY_V1_MANIFEST_SHA256.txt`
- `docs/LEGACY_V1_README_AR.md`
- `docs/LEGACY_V1_TEST_RESULTS_AR.md`
- `docs/TEST_RESULTS_AR.md`
- `docs/TEST_RESULTS_V2_2_AR.md`
- `docs/TEST_RESULTS_V2_AR.md`
- `docs/UPDATE_V2_1_EMPLOYEE_AR.md`
- `docs/UPDATE_V2_2_AR.md`
- `docs/frontend-dependency-audit.json`
- `docs/legacy-sqlserver.env.example`
- `docs/openapi-v2.json`
- `docs/openapi-v2_2.json`
- `docs/postgresql-v2-schema.sql`
- `docs/python-dependency-audit.json`
- `docs/runtime-permissions.sql`
- `docs/sqlserver-schema.sql`
- `docs/test-results-v2.txt`
- `sample-data/acceptance-example.json`
- `sample-data/v2-report-sample.pdf`
- `sample-data/v2-shift-sample.pdf`

## أصول بناء قديمة لا يستوردها index.html الحالي

2 ملفات:

- `frontend/dist/assets/index-3svv44vR.js`
- `frontend/dist/assets/index-BwTQlXo5.css`
