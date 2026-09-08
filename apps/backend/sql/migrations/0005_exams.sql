-- 0005: exams tablosu — sınav tarihine göre geri sayım planlayıcısı (Plan #9)
-- Idempotent: tüm DDL CREATE ... IF NOT EXISTS.
--
-- `exam_date` TEXT (ISO 'YYYY-MM-DD'): mevcut tarih kolonlarıyla aynı tür
-- (terms.start_date / activity_log.date) — ISO metin sıralaması tarih sıralamasıyla
-- birebir, ayrıca asyncpg native `date` nesnesi istediği için (bkz. pg_compat.py)
-- router katmanı string gönderebilsin diye TEXT tutulur.
--
-- `scope_json`: sınav kapsamındaki chapter id'lerinin JSON dizisi ('[]' = tüm ders).
-- `postmortem_json`: sınav sonrası muhasebe (Plan #44) dolduracak; şimdilik NULL.

CREATE TABLE IF NOT EXISTS exams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT NOT NULL DEFAULT 'local',
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    exam_date       TEXT NOT NULL,
    scope_json      TEXT NOT NULL DEFAULT '[]',
    postmortem_json TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exams_course        ON exams(course_id);
CREATE INDEX IF NOT EXISTS idx_exams_tenant_course ON exams(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_exams_tenant_date   ON exams(tenant_id, exam_date);
