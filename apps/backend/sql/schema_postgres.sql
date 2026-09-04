-- StuHub SaaS — Postgres şeması (Supabase SQL Editor'da elle çalıştırılır).
-- Kaynak: sql/schema.sql (SQLite, yerel/test) + KARAR-SAAS-GECISI.md kararları.
-- Fark: her içerik tablosuna `tenant_id` eklendi (satır bazlı çok kiracılılık),
-- artı `profiles` / `plans` / `subscriptions` katmanı.
--
-- Kiracı modeli: tenant_id = Supabase auth.users.id (uuid). Kiracı başına ayrı
-- şema/DB yok — tek Postgres + tenant_id kolonu (KARAR-SAAS-GECISI.md soru 2).
--
-- Uygulama şeması: `public`. `auth.users` Supabase'in kendi şeması, FK ile referans verilir.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Plan / kiracı katmanı ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS plans (
    name          TEXT PRIMARY KEY,             -- 'free' | 'pro' | 'unlimited'
    monthly_quota INTEGER,                       -- NULL = sınırsız
    price_usd_cents INTEGER NOT NULL DEFAULT 0,
    lemonsqueezy_variant_id TEXT
);

INSERT INTO plans (name, monthly_quota, price_usd_cents, lemonsqueezy_variant_id) VALUES
    ('free', 30, 0, NULL),
    ('pro', NULL, 900, NULL),
    ('unlimited', NULL, 0, NULL)
ON CONFLICT (name) DO NOTHING;

-- Her Supabase auth kullanıcısı için bir profil satırı (uygulama tarafı auto-provision eder).
CREATE TABLE IF NOT EXISTS profiles (
    id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email      TEXT NOT NULL,
    plan       TEXT NOT NULL DEFAULT 'free' REFERENCES plans(name),
    is_admin   BOOLEAN NOT NULL DEFAULT FALSE,  -- sınırsız + /api/settings erişimi
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id                 UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    lemonsqueezy_subscription_id TEXT UNIQUE,
    lemonsqueezy_customer_id  TEXT,
    plan                      TEXT NOT NULL REFERENCES plans(name),
    status                    TEXT NOT NULL DEFAULT 'active',
    current_period_end        TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON subscriptions(tenant_id);

-- ── İçerik tabloları (sql/schema.sql ile birebir + tenant_id) ──────────────

CREATE TABLE IF NOT EXISTS terms (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id  UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    start_date TEXT,
    end_date   TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS courses (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id     UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    term_id       BIGINT NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    instructor    TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS materials (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id      BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    type           TEXT NOT NULL CHECK (type IN ('textbook', 'slides', 'youtube', 'audio', 'docx', 'epub', 'image', 'text')),
    filepath       TEXT NOT NULL,
    extracted_text TEXT,
    page_count     INTEGER,
    vector_ns      TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapters (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id  UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id  BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS slides (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id    UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    chapter_id   BIGINT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    material_id  BIGINT REFERENCES materials(id) ON DELETE SET NULL,
    slide_no     INTEGER NOT NULL,
    content_text TEXT
);

CREATE TABLE IF NOT EXISTS notes (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    chapter_id     BIGINT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    content_md     TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    topics_json    TEXT NOT NULL DEFAULT '[]',
    generated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_used     TEXT
);

CREATE TABLE IF NOT EXISTS quizzes (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    chapter_id     BIGINT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    questions_json TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    quiz_id           BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_answers_json TEXT NOT NULL,
    score             REAL,
    feedback_json     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS overall_quizzes (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id      BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    questions_json TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS overall_attempts (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    overall_quiz_id BIGINT NOT NULL REFERENCES overall_quizzes(id) ON DELETE CASCADE,
    answers_json    TEXT NOT NULL,
    score_json      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS indexing_jobs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id   BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    material_id BIGINT REFERENCES materials(id) ON DELETE SET NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    progress    REAL NOT NULL DEFAULT 0,
    error       TEXT,
    kind        TEXT NOT NULL DEFAULT 'index',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS citations_ledger (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    chunk_id    TEXT,
    text        TEXT,
    source_type TEXT,
    source_id   BIGINT,
    page        INTEGER,
    slide       INTEGER
);

-- LLM çağrı günlüğü — kota bekçiliği tenant_id üzerinden aylık sayım yapar.
CREATE TABLE IF NOT EXISTS generation_logs (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    kind              TEXT NOT NULL,
    course_id         BIGINT,
    chapter_id        BIGINT,
    model             TEXT,
    provider          TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_generation_logs_tenant_month ON generation_logs(tenant_id, created_at);

-- Platform ayarları (LLM sağlayıcı anahtarları vb.) — GLOBAL, kiracıya özel DEĞİL.
-- Sadece is_admin=true profil erişebilir (bkz. src/auth.py require_admin).
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flashcard_sets (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id   BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id  BIGINT REFERENCES chapters(id) ON DELETE CASCADE,
    cards_json  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_used  TEXT
);

CREATE TABLE IF NOT EXISTS card_reviews (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id     UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    set_id        BIGINT NOT NULL REFERENCES flashcard_sets(id) ON DELETE CASCADE,
    card_index    INTEGER NOT NULL,
    ease_factor   REAL NOT NULL DEFAULT 2.5,
    interval_days REAL NOT NULL DEFAULT 0,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    due_at        TIMESTAMPTZ,
    last_rating   TEXT,
    reviewed_at   TIMESTAMPTZ,
    UNIQUE(set_id, card_index)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id      BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    role           TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content        TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    mode           TEXT NOT NULL DEFAULT 'direct' CHECK (mode IN ('direct', 'socratic', 'quiz')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS study_guides (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id    UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id    BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id   BIGINT REFERENCES chapters(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('summary', 'concept_map')),
    content_json TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_used   TEXT
);

CREATE TABLE IF NOT EXISTS essay_submissions (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    course_id   BIGINT REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id  BIGINT REFERENCES chapters(id) ON DELETE CASCADE,
    prompt      TEXT NOT NULL,
    user_text   TEXT NOT NULL,
    grade_json  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS activity_log (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    date      TEXT NOT NULL,
    kind      TEXT NOT NULL CHECK (kind IN ('note', 'quiz', 'flashcard', 'chat')),
    count     INTEGER NOT NULL DEFAULT 1,
    course_id BIGINT
);

-- Sık sorgu indeksleri (tenant_id her zaman ilk kolon — RLS + filtre birlikte hızlı)
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_tenant_day_kind_course
    ON activity_log(tenant_id, date, kind, COALESCE(course_id, 0));

-- ── Row-Level Security — savunma derinliği (uygulama zaten tenant_id filtreliyor) ──
-- API her sorguya tenant_id ekliyor (bkz. src/auth.py + routers/*), ancak RLS
-- Supabase'in service-role dışı bağlantılarında (ör. Supabase Studio, doğrudan
-- SQL erişimi) veri sızıntısına karşı ikinci savunma katmanıdır.

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'terms','courses','materials','chapters','slides','notes','quizzes',
        'quiz_attempts','overall_quizzes','overall_attempts','indexing_jobs',
        'citations_ledger','generation_logs','flashcard_sets','card_reviews',
        'chat_messages','study_guides','essay_submissions','activity_log'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (tenant_id = auth.uid()) WITH CHECK (tenant_id = auth.uid())', t
        );
    END LOOP;
END $$;

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_profile ON profiles;
CREATE POLICY own_profile ON profiles
    USING (id = auth.uid()) WITH CHECK (id = auth.uid());

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_subscriptions ON subscriptions;
CREATE POLICY own_subscriptions ON subscriptions
    USING (tenant_id = auth.uid());
