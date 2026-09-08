-- 0008: overall_quizzes/overall_attempts sınav simülasyonu alanları (Plan #35)
-- Idempotent: "duplicate column name" hoş görülür (bkz. migrations/README.md, db.py).
--
-- `mode`: 'practice' (varsayılan, mevcut davranış — anlık feedback) | 'exam' (Plan #35 —
-- cevabı açığa çıkaran alanlar sonuca kadar istemciye gönderilmez, bkz.
-- services/overall_generator.strip_exam_answers).
-- `exam_id`: sınav simülasyonunu `exams` kaydına bağlar (Plan #9'un tablosu); pratik
-- quizlerde NULL.
-- `duration_sec`: bir denemede geçen süre (saniye) — yalnızca sınav modunda dolar,
-- pratik modda NULL kalır.

ALTER TABLE overall_quizzes ADD COLUMN mode TEXT NOT NULL DEFAULT 'practice';
ALTER TABLE overall_quizzes ADD COLUMN exam_id INTEGER REFERENCES exams(id) ON DELETE SET NULL;
ALTER TABLE overall_attempts ADD COLUMN duration_sec INTEGER;

CREATE INDEX IF NOT EXISTS idx_overall_quizzes_exam ON overall_quizzes(exam_id);
