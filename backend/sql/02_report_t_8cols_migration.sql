-- ============================================================
-- 02_report_t_8cols_migration.sql
--
-- 目的:
--   report_t を「8列仕様」に固定する
--   - 既存データは保持
--   - 旧テーブルは日付付きで退避
--
-- report_t（8列）:
--   user_no, class_no, user_name,
--   start_datetime, end_datetime,
--   company_name, event_kind, result_kind
--
-- JOIN仕様（確定）:
--   report_t.user_no = user_m.user_no
--
-- 破壊的変更: あり（report_t の構造差し替え）
-- ロールバック: 退避テーブルを RENAME で戻す
-- ============================================================

BEGIN;

-- 1) 8列版を作成（別名）
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

-- 2) 既存 report_t から8列だけコピー
--    ※既存 report_t の列名が下記と一致している前提
INSERT INTO
    public.report_t_8 (
        user_no,
        class_no,
        user_name,
        start_datetime,
        end_datetime,
        company_name,
        event_kind,
        result_kind
    )
SELECT
    user_no,
    class_no,
    user_name,
    start_datetime,
    end_datetime,
    company_name,
    event_kind,
    result_kind
FROM public.report_t;

-- 3) 既存 report_t を退避（同名衝突を避けるため日付を変えて運用）
ALTER TABLE public.report_t RENAME TO report_t_old_20251214;

-- 4) 新テーブルを report_t に昇格
ALTER TABLE public.report_t_8 RENAME TO report_t;

COMMIT;

--※日付 20251214 は固定で書いてあります。
--もし“毎回変えたい”なら report_t_old_YYYYMMDD を手で変える運用にしてください（安全です）。
