import React, { useEffect, useState } from "react";
import "../student.css";

function StudentPage() {
  const [data, setData] = useState(null);
  const [studentId, setStudentId] = useState("S20240001");
  const [studentData, setStudentData] = useState(null);

  // JSON 読み込み
  useEffect(() => {
    fetch("/student_analysis.json")
      .then((res) => res.json())
      .then((json) => setData(json))
      .catch((err) => console.error("JSON 読み込みエラー:", err));
  }, []);

  // 学籍番号が変更されたら更新
  useEffect(() => {
    if (data && data[studentId]) {
      setStudentData(data[studentId]);
    }
  }, [studentId, data]);

  if (!data) return <div>読み込み中...</div>;
  if (!studentData) return <div>学生データがありません</div>;

  return (
    <div className="student-container">
      <h2>学生の受験分析レポート</h2>

      {/* 学籍番号選択 */}
      <div className="selector">
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

      <hr />

      <h3>📌 学籍番号：{studentId}</h3>

      {/* 受験企業一覧 */}
      <div className="section">
        <h4>🏢 受験企業一覧</h4>
        <ul>
          {(studentData["企業一覧"] ?? []).map((c, idx) => (
            <li key={idx}>{c}</li>
          ))}
        </ul>
      </div>

      {/* 面接日程 */}
      <div className="section">
        <h4>🗓 面接日程</h4>
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

      {/* 基本統計 */}
      <div className="section">
        <h4>📊 基本統計</h4>
        <p>受験回数：{studentData["受験回数"] ?? 0}</p>
        <p>受験期間：{studentData["受験期間"] ?? "不明"}</p>
        <p>合格率：{studentData["合格率"] ?? "不明"}</p>
      </div>

      {/* 面接形式の傾向 */}
      <div className="section">
        <h4>🎤 面接形式の傾向</h4>
        {studentData["形式傾向"] ? (
          <ul>
            {Object.entries(studentData["形式傾向"]).map(([key, val]) => (
              <li key={key}>
                {key}：{val}回
              </li>
            ))}
          </ul>
        ) : (
          <p>データなし</p>
        )}
      </div>

      {/* 面接官の傾向 */}
      <div className="section">
        <h4>👔 面接官（役職）の傾向</h4>
        {studentData["面接官傾向"] ? (
          <ul>
            {Object.entries(studentData["面接官傾向"]).map(([key, val]) => (
              <li key={key}>
                {key}：{val}回
              </li>
            ))}
          </ul>
        ) : (
          <p>データなし</p>
        )}
      </div>

      {/* AI 分析レポート */}
      <div className="section">
        <h4>🤖 AI 分析レポート</h4>
        <div className="ai-report">
          {(studentData["AI分析レポート"] ?? "")
            .split("\n")
            .map((line, idx) => (
              <p key={idx}>{line}</p>
            ))}
        </div>
      </div>
    </div>
  );
}

export default StudentPage;
