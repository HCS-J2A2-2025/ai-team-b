import { useEffect, useState } from "react";
import AppHeader from '../components/AppHeader';
import "../student.css";
import { useNavigate } from "react-router-dom";

function StudentPage() {
  const [data, setData] = useState(null);
  const [studentId, setStudentId] = useState("S20240001");
  const [role, setRole] = useState(null);
  const [studentData, setStudentData] = useState(null);
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("jobnaviUser");
    navigate("/loginpage");
  };

  // ロール確認（teacher/admin 以外アクセス不可）
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
    } catch (e) {
      console.error(e);
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

  // 学籍番号変更時に反映
  useEffect(() => {
    if (data && data[studentId]) {
      setStudentData(data[studentId]);
    }
  }, [studentId, data]);

  if (!data) return <div>読み込み中...</div>;
  if (!studentData) return <div>学生データがありません</div>;

  return (
    <div>
      <AppHeader title="学生受験分析レポート" onLogout={handleLogout} />
      <div className="student-page-root">

        {/* タイトル */}
        <h2 className="page-title">学生の受験分析レポート</h2>

        {/* ▼ おしゃれセレクタ（ここがポイント） */}
        <div className="selector-card">
          <label>学籍番号：</label>
          <select
            value={studentId}
            onChange={(e) => setStudentId(e.target.value)}
          >
            {Object.keys(data).map((sid) => (
              <option key={sid} value={sid}>
                {sid}
              </option>
            ))}
          </select>
        </div>

        <h3>📌 学籍番号：{studentId}</h3>

        {/* ▼ 以下カードデザイン */}
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
                  : "日時不明"}{" "}
                ～{" "}
                {d.終了日時
                  ? new Date(d.終了日時).toLocaleString()
                  : "日時不明"}{" "}
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
              {Object.entries(studentData["形式傾向"]).map(([key, val]) => (
                <li key={key}>{key}：{val}回</li>
              ))}
            </ul>
          ) : (
            <p>データなし</p>
          )}
        </div>

        <div className="section-card">
          <h3>👔 面接官の傾向</h3>
          {studentData["面接官傾向"] ? (
            <ul>
              {Object.entries(studentData["面接官傾向"]).map(([key, val]) => (
                <li key={key}>{key}：{val}回</li>
              ))}
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
      </div>
    </div>
  );
}

export default StudentPage;
