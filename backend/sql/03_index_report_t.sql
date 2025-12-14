-- ============================================================
-- 03_index_report_t.sql
--
-- 目的:
--   report_t の検索/集計/JOIN を高速化する
--   現状、あなたの環境では `*_new` の名前で作成済みだが、
--   このSQLは「無ければ作る」なので何度でも安全。
--
-- 破壊的変更: なし
-- ============================================================

-- 既に存在する可能性が高い（あなたの環境では存在）
CREATE INDEX IF NOT EXISTS idx_report_t_user_no_new ON public.report_t (user_no);

CREATE INDEX IF NOT EXISTS idx_report_t_start_datetime_new ON public.report_t (start_datetime);

-- もし “*_new じゃない名前” で揃えたい場合は、上を消してこちらに統一してもOK
-- CREATE INDEX IF NOT EXISTS idx_report_t_user_no
--   ON public.report_t (user_no);
-- CREATE INDEX IF NOT EXISTS idx_report_t_start_datetime
--   ON public.report_t (start_datetime);
