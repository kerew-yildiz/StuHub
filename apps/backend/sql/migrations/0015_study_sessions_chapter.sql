-- 0015: study_sessions.chapter_id — chapter görünümünde geçen aktif sürenin kaydı.
-- Idempotent: yeni kurulumda schema.sql hedef durumu zaten içerir, runner
-- "duplicate column name" hatasını hoş görür (bkz. db.py::_apply_migrations).
--
-- Süre kaynağı: frontend, chapter görünümü görünür + etkileşimliyken 45 sn'de bir
-- heartbeat gönderir; her heartbeat `duration_sec` = geçen aralık olan bir satırdır.
-- `session_id` (heartbeat UUID'si) bazında idempotenttir: ağ hatasında tekrar
-- gönderim çift saymaz, cihaz beklenmedik kapanırsa en fazla son aralık kaybolur.
--
-- Postgres (Supabase): schema_postgres.sql içindeki
--   ALTER TABLE study_sessions ADD COLUMN IF NOT EXISTS chapter_id BIGINT
--       REFERENCES chapters(id) ON DELETE CASCADE;
--   CREATE INDEX IF NOT EXISTS idx_study_sessions_tenant_chapter
--       ON study_sessions(tenant_id, chapter_id);
-- eşdeğeridir (PG şeması her açılışta idempotent uygulanır).

ALTER TABLE study_sessions
    ADD COLUMN chapter_id INTEGER REFERENCES chapters(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_study_sessions_tenant_chapter
    ON study_sessions(tenant_id, chapter_id);
