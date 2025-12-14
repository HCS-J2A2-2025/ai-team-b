# backend/sql

PostgreSQL のスキーマ作業・移行・確認を **再現性 100%**で行うための SQL 置き場です。
VSCode 拡張の「New Query」は消えることがあるため、必ずここに保存した `.sql` を使います。

## 現状の確定仕様（重要）

- `report_t.user_no` と `user_m.user_no` は **同一の JOIN キー**
  - **JOIN 条件:** `report_t.user_no = user_m.user_no`
- `user_m` に `student_no` は存在しない（現状維持方針）
- `report_t` は **8 列固定**（仕様準拠）
  - 列名: `start_datetime`, `end_datetime`（camelCase ではない）

## 実行順

1. `01_schema_migration.sql`
   - `user_m` の不足列/インデックスを整備（破壊しない）
2. `02_report_t_8cols_migration.sql`
   - `report_t` を **8 列に差し替え**（旧テーブルは退避して残す）
3. `03_index_report_t.sql`
   - `report_t` のインデックス作成（何度でも安全）
4. `99_check.sql`
   - 状態確認（列数/インデックス/JOIN 整合）

## PowerShell から実行（例）

> ※接続情報はあなたの環境に合わせて変更

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 5432 -U appuser -d appdb -f .\backend\sql\99_check.sql

--ロールバック（report_t を戻す）

  02_report_t_8cols_migration.sql 実行後、旧テーブルは report_t_old_YYYYMMDD のように退避されます。

  戻したい場合（例）:

  BEGIN;
  ALTER TABLE public.report_t RENAME TO report_t_failed;
  ALTER TABLE public.report_t_old_20251214b RENAME TO report_t;
  COMMIT;
  注意

DDL（CREATE/ALTER/DROP）実行時に、VSCode拡張の「Limit付き実行」を使うと壊れることがあります。

.sql ファイルを psql -f で流す運用が最も安全です。
```
