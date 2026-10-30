-- Run only in the restored copy before n8n reconnects.
BEGIN;
DELETE FROM shift_auth_sessions;
UPDATE shift_notification_deliveries
SET status='uncertain', lease_until=NULL,
    last_error='استعيدت نسخة احتياطية؛ تحقق من المزود قبل إعادة أي إرسال.',
    updated_at=CURRENT_TIMESTAMP
WHERE status IN ('pending','leased');
INSERT INTO shift_audit_logs(user_id,action,entity_type,entity_id,detail_json,created_at)
VALUES(NULL,'database.restored-notifications-held','database',NULL,
       '{"reason":"Restored copy: auth sessions revoked; queued notifications require review"}',CURRENT_TIMESTAMP);
COMMIT;
