-- ============================================================
-- 02_report_t_8cols_migration.sql
-- 目的: report_t を8列仕様に差し替え（旧テーブルは退避）
-- 重要: 旧テーブルのインデックス名も退避側でリネームし、現行と衝突しないようにする
-- 破壊的変更: あり（report_t 構造差し替え）
-- ============================================================

BEGIN;

DROP TABLE IF EXISTS public.report_t_8;

CREATE TABLE public.report_t_8 (
    user_no text NOT NULL,
    class_no text NOT NULL,
    user_name text NOT NULL,
    start_datetime timestamptz NOT NULL,
    end_datetime timestamptz NOT NULL,
    company_name text NOT NULL,
    event_kind text NOT NULL,
    result_kind text NOT NULL
);

-- 既存 report_t がある場合だけコピー
INSERT INTO public.report_t_8 (
    user_no, class_no, user_name,
    start_datetime, end_datetime,
    company_name, event_kind, result_kind
)
SELECT
    user_no, class_no, user_name,
    start_datetime, end_datetime,
    company_name, event_kind, result_kind
FROM public.report_t
WHERE to_regclass('public.report_t') IS NOT NULL;

-- 既存 report_t を report_t_old_YYYYMMDD[_n] に退避し、退避側インデックス名もまとめて変更
DO $$
DECLARE
    base_name text := 'report_t_old_' || to_char(current_date, 'YYYYMMDD');
    backup_name text := base_name;
    n int := 0;
    r record;
    new_base text;
    new_name text;
    k int;
BEGIN
    IF to_regclass('public.report_t') IS NULL THEN
        RETURN;
    END IF;

    WHILE to_regclass('public.' || quote_ident(backup_name)) IS NOT NULL LOOP
        n := n + 1;
        backup_name := base_name || '_' || n;
    END LOOP;

    EXECUTE format('ALTER TABLE public.report_t RENAME TO %I', backup_name);

    -- 退避側インデックスをリネーム（63文字制限＋衝突回避）
    FOR r IN
        SELECT c.relname AS index_name
        FROM pg_class c
        JOIN pg_index ix ON ix.indexrelid = c.oid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace ns ON ns.oid = c.relnamespace
        WHERE ns.nspname = 'public'
          AND t.relname = backup_name
    LOOP
        new_base := left(r.index_name || '__' || backup_name, 55);
        new_name := new_base;
        k := 0;

        WHILE to_regclass('public.' || quote_ident(new_name)) IS NOT NULL LOOP
            k := k + 1;
            new_name := left(new_base, 55 - length(k::text) - 1) || '_' || k::text;
        END LOOP;

        EXECUTE format('ALTER INDEX public.%I RENAME TO %I', r.index_name, new_name);
    END LOOP;
END $$;

-- 新テーブルを昇格
ALTER TABLE public.report_t_8 RENAME TO report_t;

COMMIT;
