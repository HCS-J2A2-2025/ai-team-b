// frontend/src/pages/FollowupDashboard.jsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Filters from "../components/Filters";
import StudentTable from "../components/StudentTable";
import StudentDetail from "../components/StudentDetail";
import "../css/FollowupDashboard.css";

export default function FollowupDashboard() {
  const navigate = useNavigate();

  const [role, setRole] = useState(null);

  const [filters, setFilters] = useState({
    academic_year_start: 2025,
    course_classes: [],
    class_nos: [],
    include_excluded_good: false,
    only_followup_candidate: false,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [data, setData] = useState({ group_meta: {}, students: [] });
  const [selected, setSelected] = useState(null);

  // =========================
  // 認証チェック
  // =========================
  useEffect(() => {
    const stored = localStorage.getItem("jobnaviUser");
    if (!stored) {
      navigate("/loginpage");
      return;
    }

    try {
      const u = JSON.parse(stored);
      if (u.role !== "teacher" && u.role !== "admin") {
        navigate("/loginpage");
        return;
      }
      setRole(u.role);
    } catch {
      navigate("/loginpage");
    }
  }, [navigate]);

  // =========================
  // API 呼び出し
  // =========================
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    const API_BASE =
      process.env.REACT_APP_API_BASE_URL || "http://localhost:8000";

    try {
      const stored = localStorage.getItem("jobnaviUser");
      const roleValue = stored ? JSON.parse(stored)?.role : null;

      const res = await fetch(`${API_BASE}/followup/analysis`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-ROLE": roleValue ?? "",
        },
        body: JSON.stringify(filters),
      });

      if (res.status === 403) {
        alert("権限がありません。ログインし直してください。");
        navigate("/loginpage");
        return;
      }

      if (!res.ok) {
        // ★ 起動途中などはここに来る
        throw new Error(`API error ${res.status}`);
      }

      const json = await res.json();

      if (
        !json ||
        typeof json !== "object" ||
        !Array.isArray(json.students) ||
        typeof json.group_meta !== "object"
      ) {
        throw new Error("Invalid API response");
      }

      setData(json);
      setSelected(null);
    } catch (e) {
      console.warn("followup analysis retryable error:", e);
      setError("サーバー起動中、または一時的に接続できません。");
    } finally {
      setLoading(false);
    }
  }, [filters, navigate]);

  // =========================
  // 初回ロード
  // =========================
  useEffect(() => {
    if (!role) return;

    // ★ バック起動直後対策：少し待つ
    const timer = setTimeout(() => {
      refresh();
    }, 300);

    return () => clearTimeout(timer);
  }, [role, refresh]);

  // =========================
  // 選択中学生のメタ
  // =========================
  const selectedMeta = useMemo(() => {
    if (!selected) return null;
    return data.group_meta?.[selected.course_class] ?? null;
  }, [selected, data.group_meta]);

  // =========================
  // 描画
  // =========================
  return (
    <div style={{ padding: 16 }}>
      <h2>就活フォロー分析（学年年度 / 学科・学年）</h2>

      <Filters
        filters={filters}
        setFilters={setFilters}
        onApply={refresh}
        loading={loading}
      />

      {/* ローディング */}
      {loading && <div style={{ marginTop: 8 }}>読み込み中...</div>}

      {/* エラー（致命的ではない） */}
      {error && !loading && (
        <div style={{ marginTop: 8, color: "red" }}>
          {error}
          <div style={{ marginTop: 4 }}>
            <button onClick={refresh}>再読み込み</button>
          </div>
        </div>
      )}

      {/* 正常表示 */}
      {!loading && !error && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.2fr 1fr",
            gap: 16,
            marginTop: 12,
          }}
        >
          <div>
            <StudentTable
              students={data.students}
              onSelect={setSelected}
              selectedUserNo={selected?.user_no}
            />
          </div>
          <div>
            <StudentDetail student={selected} groupMeta={selectedMeta} />
          </div>
        </div>
      )}
    </div>
  );
}
