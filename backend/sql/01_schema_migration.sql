-- ============================================================
-- 01_schema_migration.sql
-- 目的: user_m を現状維持で整備（JOINキーは user_no）
-- 破壊的変更: なし
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.user_m (
    user_no text PRIMARY KEY
);

ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS class_no text;
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS user_name text;
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS authority text; -- student/teacher/admin 等
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS status text;    -- valid/invalid 等
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS class_no_old text;

CREATE INDEX IF NOT EXISTS idx_user_m_authority_status ON public.user_m (authority, status);
CREATE INDEX IF NOT EXISTS idx_user_m_class_no ON public.user_m (class_no);

COMMIT;
