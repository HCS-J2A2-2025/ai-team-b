// frontend/src/components/StudentTable.jsx

import React from "react";

// Badge component for overall and phase statuses
function StatusBadge({ status }) {
  if (!status) return null;

  const map = {
    danger: { label: "要対応", color: "#e53935", icon: "🔴" },
    warn: { label: "注意", color: "#fb8c00", icon: "🟠" },
    ok: { label: "基準内", color: "#43a047", icon: "🟢" },
  };

  const s = map[status.level] ?? map.ok;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 12,
        color: s.color,
        fontWeight: 600,
      }}
    >
      {s.icon} {s.label}
    </span>
  );
}

export default function StudentTable({ students, onSelect, selectedUserNo }) {
  if (!students || students.length === 0) {
    return <div>データがありません</div>;
  }

  // グループ分け: classification で
  const groups = {
    urgent: [],
    followup: [],
    ok: [],
  };
  students.forEach((s) => {
    const cls = s.classification || 'ok';
    if (groups[cls]) groups[cls].push(s);
  });

  // 同グループ内でソート: priority_score 降順
  const sortByPriority = (arr) => {
    return arr.slice().sort((a, b) => {
      const ap = a.priority_score ?? 0;
      const bp = b.priority_score ?? 0;
      return bp - ap;
    });
  };

  const renderRows = (arr) => {
    return sortByPriority(arr).map((s) => {
      const selected = selectedUserNo === s.user_no;
      // 背景色を分類ごとに設定
      let rowStyle = {};
      if (s.classification === 'urgent') {
        rowStyle = { backgroundColor: '#ffebee' };
      } else if (s.classification === 'followup') {
        rowStyle = { backgroundColor: '#fff8e1' };
      } else if (s.classification === 'ok') {
        rowStyle = { backgroundColor: '#e8f5e9' };
      }
      return (
        <tr
          key={s.user_no}
          className={selected ? 'selected' : ''}
          onClick={() => onSelect(s)}
          style={rowStyle}
        >
          <td>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
              }}
            >
              <StatusBadge status={{ level: s.overall_level }} />
              {s.overall_reason && (
                <span style={{ fontSize: 10, color: '#555' }}>{s.overall_reason}</span>
              )}
            </div>
          </td>
          <td>{s.user_no}</td>
          <td>{s.user_name}</td>
          <td>{s.course_class}</td>
          <td>
            <StatusBadge status={s.briefing_status} />
          </td>
          <td>
            <StatusBadge status={s.interview_status} />
          </td>
        </tr>
      );
    });
  };

  return (
    <div className="student-table-wrapper">
      {/* 緊急対応 */}
      {groups.urgent.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div
            style={{ fontWeight: 700, color: '#e53935', marginBottom: 4 }}
          >
            緊急対応
          </div>
          <table className="student-table">
            <thead>
              <tr>
                <th>総合</th>
                <th>学籍番号</th>
                <th>氏名</th>
                <th>学科</th>
                <th>説明会</th>
                <th>面接</th>
              </tr>
            </thead>
            <tbody>{renderRows(groups.urgent)}</tbody>
          </table>
        </div>
      )}

      {/* 要フォロー */}
      {groups.followup.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div
            style={{ fontWeight: 700, color: '#fb8c00', marginBottom: 4 }}
          >
            要フォロー
          </div>
          <table className="student-table">
            <thead>
              <tr>
                <th>総合</th>
                <th>学籍番号</th>
                <th>氏名</th>
                <th>学科</th>
                <th>説明会</th>
                <th>面接</th>
              </tr>
            </thead>
            <tbody>{renderRows(groups.followup)}</tbody>
          </table>
        </div>
      )}

      {/* 順調 */}
      {groups.ok.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div
            style={{ fontWeight: 700, color: '#43a047', marginBottom: 4 }}
          >
            順調
          </div>
          <table className="student-table">
            <thead>
              <tr>
                <th>総合</th>
                <th>学籍番号</th>
                <th>氏名</th>
                <th>学科</th>
                <th>説明会</th>
                <th>面接</th>
              </tr>
            </thead>
            <tbody>{renderRows(groups.ok)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
