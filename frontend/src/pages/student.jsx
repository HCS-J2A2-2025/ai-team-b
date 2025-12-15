import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import "../student.css";
import { useNavigate } from "react-router-dom";

function StudentPage() {
  const [data, setData] = useState(null);
  const [studentId, setStudentId] = useState("");
  const [role, setRole] = useState(null);
  const [studentData, setStudentData] = useState(null);

  // ▼ 追加：検索用
  const [keyword, setKeyword] = useState("");
  const [suggestions, setSuggestions] = useState([]);

  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("jobnaviUser");
    navigate("/loginpage");
  };

  // ロール確認
  useEffect(() => {
    const stored = localStorage.getItem("jobnaviUser");
    if (!stored) {
      navigate("/loginpage");
      return;
    }
    try {
      const user = JSON.parse(stored);
      if (user.role !== "teacher" && user.role !== "admin") {
        navigate("/loginpage");
        return;
      }
      setRole(user.role);
    } catch {
      navigate("/loginpage");
    }
  }, [navigate]);

  // JSON 読み込み
  useEffect(() => {
    fetch("/student_analysis.json")
      .then((res) => res.json())
      .then((json) => setData(json))
      .catch((err) => console.error("JSON 読み込みエラー:", err));
  }, []);

  // 学籍番号確定時に学生データ反映
  useEffect(() => {
    if (data && studentId && data[studentId]) {
      setStudentData(data[studentId]);
    } else {
      setStudentData(null);
    }
  }, [studentId, data]);

  // ▼ 学籍番号検索（サジェスト）
  const handleKeywordChange = (e) => {
    const value = e.target.value;
    setKeyword(value);

    if (!data || !value) {
      setSuggestions([]);
      return;
    }

    const list = Object.keys(data).filter((sid) =>
      sid.toLowerCase().includes(value.toLowerCase())
    );

    setSuggestions(list);
  };

  const handleSuggestionClick = (sid) => {
    setStudentId(sid);
    setKeyword(sid);
    setSuggestions([]);
  };

  if (!data) return <div>読み込み中...</div>;

  return (
    <div>
      <AppHeader title="学生受験分析レポート" onLogout={handleLogout} />

      <div className="student-page-root">
        <h2 className="page-title">学生の受験分析レポート</h2>

        {/* ▼ 学籍番号検索（プルダウン → 検索置き換え） */}
        <div className="selector-card">
          <label>学籍番号：</label>

          <div className="search-wrapper">
            <input
              type="text"
              className="search-input"
              placeholder="学籍番号を検索（例：S20240001）"
              value={keyword}
              onChange={handleKeywordChange}
            />

            {suggestions.length > 0 && (
              <div className="suggest-panel">
                {suggestions.map((sid) => (
                  <div
                    key={sid}
                    className="suggest-row"
                    onClick={() => handleSuggestionClick(sid)}
                  >
                    {sid}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {studentId && <h3>📌 学籍番号：{studentId}</h3>}

        {!studentData && studentId && (
          <p style={{ color: "#d32f2f" }}>
            該当する学生データがありません
          </p>
        )}

        {studentData && (
          <>
            <div className="section-card">
              <h3>🏢 受験企業一覧</h3>
              <ul>
                {(studentData["企業一覧"] ?? []).map((c, idx) => (
                  <li key={idx}>{c}</li>
                ))}
              </ul>
            </div>

            <div className="section-card">
              <h3>🗓 面接日程</h3>
              <ul>
                {(studentData["面接日程"] ?? []).map((d, idx) => (
                  <li key={idx}>
                    <strong>{d["企業名"]}</strong>：
                    {d.start_datetime
                      ? new Date(d.start_datetime).toLocaleString()
                      : "日時不明"}
                    ～{" "}
                    {d.終了日時
                      ? new Date(d.終了日時).toLocaleString()
                      : "日時不明"}
                    （結果：{d.result_status ?? "不明"}）
                  </li>
                ))}
              </ul>
            </div>

            <div className="section-card">
              <h3>📊 基本統計</h3>
              <p>受験回数：{studentData["受験回数"] ?? 0}</p>
              <p>受験期間：{studentData["受験期間"] ?? "不明"}</p>
              <p>合格率：{studentData["合格率"] ?? "不明"}</p>
            </div>

            <div className="section-card">
              <h3>🎤 面接形式の傾向</h3>
              {studentData["形式傾向"] ? (
                <ul>
                  {Object.entries(studentData["形式傾向"]).map(
                    ([key, val]) => (
                      <li key={key}>
                        {key}：{val}回
                      </li>
                    )
                  )}
                </ul>
              ) : (
                <p>データなし</p>
              )}
            </div>

            <div className="section-card">
              <h3>👔 面接官の傾向</h3>
              {studentData["面接官傾向"] ? (
                <ul>
                  {Object.entries(studentData["面接官傾向"]).map(
                    ([key, val]) => (
                      <li key={key}>
                        {key}：{val}回
                      </li>
                    )
                  )}
                </ul>
              ) : (
                <p>データなし</p>
              )}
            </div>

            <div className="section-card">
              <h3>🤖 AI分析レポート</h3>
              <div className="ai-report">
                {(studentData["AI分析レポート"] ?? "")
                  .split("\n")
                  .map((line, idx) => (
                    <p key={idx}>{line}</p>
                  ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default StudentPage;
