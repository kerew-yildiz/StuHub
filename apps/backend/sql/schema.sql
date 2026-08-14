-- StuHub DS — SQLite şeması (Faz 0.2)
-- Kaynak: PROJE_YOL_HARITASI.md Bölüm 3 (tek doğruluk kaynağı).
-- Idempotent: CREATE TABLE IF NOT EXISTS — init_db her açılışta güvenle uygular.
-- Migration politikası: sql/migrations/README.md

PRAGMA foreign_keys = ON;

-- Dönem klasörleri (ör. "2026 Bahar")
CREATE TABLE IF NOT EXISTS terms (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    start_date TEXT,
    end_date   TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Dersler (bir dönem altında)
CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id       INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    instructor    TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Materyaller: ders kitabı PDF'i ya da hoca sunumu (guide slides)
CREATE TABLE IF NOT EXISTS materials (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    type           TEXT NOT NULL CHECK (type IN ('textbook', 'slides')),
    filepath       TEXT NOT NULL,
    extracted_text TEXT,
    page_count     INTEGER,
    vector_ns      TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Chapter'lar (ders içi bölümler)
CREATE TABLE IF NOT EXISTS chapters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id  INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Slide bazlı atıf granülaritesi (Faz 2)
CREATE TABLE IF NOT EXISTS slides (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id   INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    material_id  INTEGER REFERENCES materials(id) ON DELETE SET NULL,
    slide_no     INTEGER NOT NULL,
    content_text TEXT
);

-- Üretilen notlar (markdown + atıf/topic JSON'ları)
CREATE TABLE IF NOT EXISTS notes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id     INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    content_md     TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    topics_json    TEXT NOT NULL DEFAULT '[]',
    generated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_used     TEXT
);

-- Quiz'ler (sorular denormalize JSON; v4.3: type kaldırıldı)
CREATE TABLE IF NOT EXISTS quizzes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id     INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    questions_json TEXT NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id           INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_answers_json TEXT NOT NULL,
    score             REAL,
    feedback_json     TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overall_quizzes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    questions_json TEXT NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overall_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    overall_quiz_id INTEGER NOT NULL REFERENCES overall_quizzes(id) ON DELETE CASCADE,
    answers_json    TEXT NOT NULL,
    score_json      TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Vektör indeksleme işleri (arka plan, Faz 2.2)
CREATE TABLE IF NOT EXISTS indexing_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    progress    REAL NOT NULL DEFAULT 0,
    error       TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Atıf defteri (chunk → kaynak eşlemesi; doğrulama Faz 3+)
CREATE TABLE IF NOT EXISTS citations_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id    TEXT,
    text        TEXT,
    source_type TEXT,
    source_id   INTEGER,
    page        INTEGER,
    slide       INTEGER
);

-- LLM çağrı günlüğü (maliyet gözetimi — Ücretsizlik Ajanı denetimi)
CREATE TABLE IF NOT EXISTS generation_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    kind              TEXT NOT NULL,
    course_id         INTEGER,
    chapter_id        INTEGER,
    model             TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Anahtar/değer ayarları (API anahtarı, model adı vb. — yerel, commit dışı)
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Sık sorgu indeksleri
CREATE INDEX IF NOT EXISTS idx_courses_term        ON courses(term_id);
CREATE INDEX IF NOT EXISTS idx_materials_course    ON materials(course_id);
CREATE INDEX IF NOT EXISTS idx_chapters_course     ON chapters(course_id);
CREATE INDEX IF NOT EXISTS idx_slides_chapter      ON slides(chapter_id);
CREATE INDEX IF NOT EXISTS idx_notes_chapter       ON notes(chapter_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_chapter     ON quizzes(chapter_id);
CREATE INDEX IF NOT EXISTS idx_overall_quizzes_course ON overall_quizzes(course_id);
