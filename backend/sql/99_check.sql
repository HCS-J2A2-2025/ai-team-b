-- ============================================================
-- 99_check.sql
-- 目的: 現状の整合性チェック（列数/インデックス/JOIN）
-- ============================================================

SELECT COUNT(*) AS report_t_cols
FROM information_schema.columns
WHERE table_schema='public' AND table_name='report_t';

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='public' AND table_name='report_t'
ORDER BY ordinal_position;

SELECT COUNT(*) AS report_t_rows FROM public.report_t;
SELECT COUNT(*) AS user_m_rows FROM public.user_m;

SELECT indexname
FROM pg_indexes
WHERE schemaname='public' AND tablename='report_t'
ORDER BY indexname;

SELECT
  COUNT(*) AS report_rows,
  COUNT(*) FILTER (WHERE u.user_no IS NOT NULL) AS matched_rows
FROM public.report_t r
LEFT JOIN public.user_m u ON u.user_no = r.user_no;

SELECT r.user_no, COUNT(*) AS cnt
FROM public.report_t r
LEFT JOIN public.user_m u ON u.user_no = r.user_no
WHERE u.user_no IS NULL
GROUP BY r.user_no
ORDER BY cnt DESC
LIMIT 20;

SELECT tablename
FROM pg_tables
WHERE schemaname='public' AND tablename LIKE 'report_t_old_%'
ORDER BY tablename DESC;
