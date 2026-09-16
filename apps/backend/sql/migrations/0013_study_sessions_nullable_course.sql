-- 0013: study_sessions.course_id nullable — genel (ders dışı) kullanım süresi kaydı.
-- Idempotent: her DDL/pragma idempotent.
--
-- Uygulama genelinde geçirilen aktif süre (ders context'i dışındaki sayfalar dahil)
-- artık otomatik kaydediliyor (kullanıcı sıkıntı kaydı #2). Ders context'inde
-- course_id dolu gelir; global sayfalarda NULL. Haftalık toplam (GET /study-sessions/
-- weekly) course_id'ye bakmaz — tüm oturumları toplar.
--
-- SQLite: course_id'yi (course_id,...) index'iyle birlikte yeniden oluşturmadan
-- nullable yapmak zor; legacy_alter_table pragma'sı ile CREATE TABLE + kopya
-- kullanılıyor. Taze kurulumlarda schema.sql hedef durumu zaten nullable içerir
-- (bu migration yalnızca 0010 ile kurulmuş mevcut DB'ler için geçerlidir).
--
-- Postgres (Supabase): ALTER TABLE study_sessions ALTER COLUMN course_id DROP NOT NULL;
-- NOT NULL kısıtı adıyla (study_sessions_course_id_not_null) bulunuyorsa önce DROP.

PRAGMA legacy_alter_table = ON;

CREATE TABLE IF NOT EXISTS study_sessions_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    TEXT NOT NULL DEFAULT 'local',
    course_id    INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    session_id   TEXT NOT NULL,
    duration_sec INTEGER NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO study_sessions_new (id, tenant_id, course_id, session_id, duration_sec, created_at)
SELECT id, tenant_id, course_id, session_id, duration_sec, created_at FROM study_sessions;

DROP TABLE study_sessions;
ALTER TABLE study_sessions_new RENAME TO study_sessions;

CREATE INDEX IF NOT EXISTS idx_study_sessions_tenant_course
    ON study_sessions(tenant_id, course_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_sessions_session
    ON study_sessions(tenant_id, session_id);

PRAGMA legacy_alter_table = OFF;
