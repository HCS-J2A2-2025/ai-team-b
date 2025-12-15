# backend/sql

PostgreSQL のスキーマ作業・移行・確認を **再現性 100%**で行うための SQL 置き場です。

## 現状の確定仕様（重要）

- `report_t.user_no` と `user_m.user_no` は同一の JOIN キー（`report_t.user_no = user_m.user_no`）
- `report_t` は 8 列固定（`start_datetime`, `end_datetime`）

## 実行順

1. `01_schema_migration.sql`
2. `02_report_t_8cols_migration.sql`
   - 旧 `report_t` は自動で `report_t_old_YYYYMMDD[_n]` に退避
   - **退避側インデックス名も自動リネーム**（現行 `report_t` のインデックス作成と衝突しない）
3. `03_index_report_t.sql`
   - canonical 名で統一: `idx_report_t_user_no`, `idx_report_t_start_datetime`, `idx_report_t_company_name`
4. `99_check.sql`

## ロールバック例

```sql
BEGIN;
ALTER TABLE public.report_t RENAME TO report_t_failed;
ALTER TABLE public.report_t_old_20251215 RENAME TO report_t;
COMMIT;
```

↓----------------------------------------------------------------------------------------
「どの環境でも再現できる」「Docker がある場所に移動してから、psql で migration を流すまで」を
完全に一般化した手順としてまとめます。

以下は Docker Compose + PostgreSQL + psql を想定した標準形です。

0️⃣ 前提（一般化）

docker-compose.yml があるディレクトリを プロジェクトルートと呼ぶ

PostgreSQL サービス名を db（← 違う場合は置き換える）

DB 名：appdb

ユーザー：postgres

SQL は コンテナ内パス /backend/sql/\*.sql にある
（ホスト → コンテナに volume マウントされている前提）

1️⃣ Docker がある場所へ移動（ホスト側）
cd /path/to/your/project

例（Windows + PowerShell）：

cd C:\Users\yuuki\OneDrive\ドキュメント\ゼミ\ai-team-b

✅ ここで docker-compose.yml が見える状態が正解

2️⃣ Docker を起動（未起動なら）
docker compose up -d

確認：

docker compose ps

db（PostgreSQL）が running になっていれば OK。

3️⃣ PostgreSQL コンテナに入る
方法 A（最も一般的・安全）
docker compose exec db bash

※ Alpine の場合：

docker compose exec db sh

4️⃣ コンテナ内で psql を起動
psql -U postgres -d appdb

成功すると：

appdb=#

5️⃣ SQL ディレクトリにいることを確認
\! pwd
\! ls backend/sql

ここで以下が見えれば OK：

01_schema_migration.sql
02_report_t_8cols_migration.sql
03_index_report_t.sql
99_check.sql

見えない場合
→ volume マウントのパスが違う
→ その場合は \! find / -name 01_schema_migration.sql で探す

6️⃣ Migration を実行（あなたが書いたコマンド）
\i backend/sql/01_schema_migration.sql
\i backend/sql/02_report_t_8cols_migration.sql
\i backend/sql/03_index_report_t.sql
\i backend/sql/99_check.sql

7️⃣ 終了
\q
exit

🔁 これを「完全一般化」したテンプレ
毎回やるコマンド（ホスト）
cd <docker-compose.yml がある場所>
docker compose up -d
docker compose exec <db_service_name> bash

毎回やるコマンド（コンテナ内）
psql -U <db_user> -d <db_name>

\i <sql_dir>/01_schema_migration.sql
\i <sql_dir>/02_report_t_8cols_migration.sql
\i <sql_dir>/03_index_report_t.sql
\i <sql_dir>/99_check.sql
