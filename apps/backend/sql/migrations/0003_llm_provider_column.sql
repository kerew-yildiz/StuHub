-- 0003: generation_logs'a provider kolonu — ücretsiz LLM sağlayıcı zinciri (Kerem kararı, 2026-09-02)
-- Idempotent: "duplicate column name" hoş görülür (bkz. migrations/README.md).

ALTER TABLE generation_logs ADD COLUMN provider TEXT;
