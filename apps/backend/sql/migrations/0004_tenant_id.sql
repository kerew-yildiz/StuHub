-- 0004: tenant_id kolonu — SaaS kiracı izolasyonu (KARAR-SAAS-GECISI.md soru 2)
-- Idempotent: "duplicate column name" hoş görülür (bkz. migrations/README.md).
-- Yerel/tek-kullanıcı kurulumlar için varsayılan 'local' — mevcut satırlar bu
-- değeri alır, davranış değişmez (auth yalnızca settings.saas_mode true iken
-- zorunlu, bkz. src/auth.py).

ALTER TABLE terms ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE courses ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE materials ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE chapters ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE slides ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE notes ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE quizzes ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE quiz_attempts ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE overall_quizzes ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE overall_attempts ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE indexing_jobs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE citations_ledger ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE generation_logs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE flashcard_sets ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE card_reviews ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE chat_messages ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE study_guides ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE essay_submissions ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';
ALTER TABLE activity_log ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local';

CREATE INDEX IF NOT EXISTS idx_terms_tenant             ON terms(tenant_id);
CREATE INDEX IF NOT EXISTS idx_courses_tenant_term       ON courses(tenant_id, term_id);
CREATE INDEX IF NOT EXISTS idx_materials_tenant_course   ON materials(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_chapters_tenant_course    ON chapters(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_slides_tenant_chapter     ON slides(tenant_id, chapter_id);
CREATE INDEX IF NOT EXISTS idx_notes_tenant_chapter      ON notes(tenant_id, chapter_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_tenant_chapter    ON quizzes(tenant_id, chapter_id);
CREATE INDEX IF NOT EXISTS idx_overall_quizzes_tenant    ON overall_quizzes(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_tenant     ON flashcard_sets(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_card_reviews_tenant_due   ON card_reviews(tenant_id, due_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant      ON chat_messages(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_study_guides_tenant       ON study_guides(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_essay_submissions_tenant  ON essay_submissions(tenant_id, course_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_tenant_date  ON activity_log(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_generation_logs_tenant_month ON generation_logs(tenant_id, created_at);

-- Eski (tenant_id'siz) tekillik index'ini kiracı-farkında olacak şekilde yeniden kurar —
-- yükseltmede SaaS'ta iki kiracının aynı gün/tür/course_id'de çakışmasını önler.
DROP INDEX IF EXISTS idx_activity_day_kind_course;
CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_day_kind_course
    ON activity_log(tenant_id, date, kind, COALESCE(course_id, 0));
