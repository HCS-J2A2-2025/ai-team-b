---

# `backend/sql/01_schema_migration.sql`

```sql
-- ============================================================
-- 01_schema_migration.sql
--
-- 目的:
--   現状維持（JOINキーは user_no 同士）で user_m を整備する
--   - user_m が無ければ作る
--   - 必要な列が無ければ追加（破壊しない）
--   - よく使う検索用インデックスを付与
--
-- JOIN仕様（確定）:
--   report_t.user_no = user_m.user_no
--
-- 破壊的変更: なし
-- ============================================================

BEGIN;

-- user_m が無ければ作成（現状の確定列構成）
CREATE TABLE IF NOT EXISTS public.user_m (
    user_no      text PRIMARY KEY,
    class_no     text NOT NULL,
    user_name    text NOT NULL,
    authority    text NOT NULL, -- student / admin 等
    status       text NOT NULL, -- valid / invalid 等
    class_no_old text           -- 任意（既に存在するなら維持）
);

-- 既存環境に合わせて、足りない列だけ追加
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS class_no     text;
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS user_name    text;
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS authority    text;
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS status       text;
ALTER TABLE public.user_m ADD COLUMN IF NOT EXISTS class_no_old text;

-- NOT NULL 付与は既存データ次第で失敗し得るため、ここでは強制しない
-- （必要なら別途クレンジング後に追加する）

-- よく使う検索を支えるインデックス
CREATE INDEX IF NOT EXISTS idx_user_m_authority_status
  ON public.user_m (authority, status);

CREATE INDEX IF NOT EXISTS idx_user_m_class_no
  ON public.user_m (class_no);

COMMIT;
