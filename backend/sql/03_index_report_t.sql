-- ============================================================
-- 03_index_report_t.sql
-- 目的: report_t の検索/集計/JOIN を高速化（canonical 名で統一）
-- 破壊的変更: なし
-- ============================================================

BEGIN;

CREATE INDEX IF NOT EXISTS idx_report_t_user_no
  ON public.report_t (user_no);

CREATE INDEX IF NOT EXISTS idx_report_t_start_datetime
  ON public.report_t (start_datetime);

CREATE INDEX IF NOT EXISTS idx_report_t_company_name
  ON public.report_t (company_name);

COMMIT;
