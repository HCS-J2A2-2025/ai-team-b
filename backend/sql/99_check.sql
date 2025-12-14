-- ============================================================
-- 99_check.sql
--
-- 目的:
--   現状の整合性チェック（仕様どおりか、JOINできるか）
-- ============================================================

-- report_t が8列か
SELECT COUNT(*) AS report_t_cols
FROM information_schema.columns
WHERE
    table_schema = 'public'
    AND table_name = 'report_t';

-- report_t の列一覧
SELECT column_name, data_type
FROM information_schema.columns
WHERE
    table_schema = 'public'
    AND table_name = 'report_t'
ORDER BY ordinal_position;

-- report_t の件数
SELECT COUNT(*) AS report_t_rows FROM public.report_t;

-- user_m の件数
SELECT COUNT(*) AS user_m_rows FROM public.user_m;

-- report_t のインデックス確認
SELECT indexname
FROM pg_indexes
WHERE
    schemaname = 'public'
    AND tablename = 'report_t'
ORDER BY indexname;

-- JOIN整合性（確定仕様：user_no 同士で全件一致が期待）
SELECT COUNT(*) AS report_rows, COUNT(*) FILTER (
        WHERE
            u.user_no IS NOT NULL
    ) AS matched_rows
FROM public.report_t r
    LEFT JOIN public.user_m u ON u.user_no = r.user_no;

-- もし不一致がある場合のサンプル表示
SELECT r.user_no, COUNT(*) AS cnt
FROM public.report_t r
    LEFT JOIN public.user_m u ON u.user_no = r.user_no
WHERE
    u.user_no IS NULL
GROUP BY
    r.user_no
ORDER BY cnt DESC
LIMIT 20;
