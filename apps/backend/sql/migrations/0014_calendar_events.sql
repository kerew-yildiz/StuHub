-- 0014: calendar_events tablosu — takvim sayfasına sınav/ödev notu ekleme (sıkıntı #4).
-- Idempotent: CREATE TABLE/INDEX IF NOT EXISTS.
--
-- Kullanıcı aylık takvimde bir güne "sınav" veya "ödev" notu ekleyebilir;
-- not alınan günler takvimde parlak gösterilir, hover'da içerik görür.
-- Sınavlar ayrıca exams tablosundan otomatik gelir (kind='exam' manuel notlar
-- exams ile karışmasın diye ayrı kind'ler kullanılır: 'assignment' / 'custom').
--
-- Postgres (Supabase) karşılığı sql/schema_postgres.sql'de tutulur.

CREATE TABLE IF NOT EXISTS calendar_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id  TEXT NOT NULL DEFAULT 'local',
    course_id  INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    event_date TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'custom',
    title      TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_tenant_date
    ON calendar_events(tenant_id, event_date);
CREATE INDEX IF NOT EXISTS idx_calendar_events_course
    ON calendar_events(course_id);
