-- 0010: study_sessions tablosu — pomodoro çalışma oturumu kayıtları (Plan #14).
-- Idempotent: CREATE TABLE/INDEX IF NOT EXISTS.
--
-- Her satır tamamlanmış bir pomodoro döngüsünü (25dk çalışma + 5dk mola) temsil eder.
-- Ayrı bir tablo tercih edildi: `activity_log` günlük TOPLAM sayaç tutar (kind başına
-- tek satır/gün, UNIQUE(tenant_id,date,kind,course_id)), bu yüzden oturum başına
-- `session_id`/`duration_sec` gibi ayrık alanlar activity_log'un birleştirme (upsert
-- + count artırma) modeliyle uyuşmaz — her oturumun kendi satırı gerekir.
--
-- `session_id` istemcinin ürettiği kararlı bir kimlik (örn. crypto.randomUUID()) —
-- ağ tekrarında (retry) aynı oturumun iki kez yazılmasını UNIQUE indeksle engeller;
-- uç bu durumda mevcut satırı olduğu gibi döner (idempotent POST).
--
-- Postgres (Supabase) karşılığı sql/schema_postgres.sql'de tutulur; mevcut canlı
-- veritabanı için elle uygulanacak eşdeğer:
--   CREATE TABLE IF NOT EXISTS study_sessions (
--       id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
--       tenant_id    UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
--       course_id    BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
--       session_id   TEXT NOT NULL,
--       duration_sec INTEGER NOT NULL,
--       created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
--   );
--   CREATE INDEX IF NOT EXISTS idx_study_sessions_tenant_course
--       ON study_sessions(tenant_id, course_id);
--   CREATE UNIQUE INDEX IF NOT EXISTS idx_study_sessions_session
--       ON study_sessions(tenant_id, session_id);
--   (RLS FOREACH döngüsüne 'study_sessions' eklenmeli.)

CREATE TABLE IF NOT EXISTS study_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    TEXT NOT NULL DEFAULT 'local',
    course_id    INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    session_id   TEXT NOT NULL,
    duration_sec INTEGER NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_study_sessions_tenant_course
    ON study_sessions(tenant_id, course_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_sessions_session
    ON study_sessions(tenant_id, session_id);
