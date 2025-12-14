// frontend/src/components/StudentDetail.jsx

function explain(status, label) {
  if (!status) return `${label}の情報がありません。`;

  if (status.status === "not_started") {
    return `${label}がまだ開始されていません。早急な対応が必要です。`;
  }

  if (status.level === "danger") {
    // danger: show delay days if available, else use delay percent
    if (status.delay_days != null) {
      return `${label}の開始が大きく遅れています（${status.delay_days}日遅れ）。`;
    }
    if (status.delay_percent != null) {
      return `${label}の開始が大きく遅れています（遅れ度${Math.round(status.delay_percent)}%）。`;
    }
    return `${label}の開始が大きく遅れています。`;
  }

  if (status.level === "warn") {
    if (status.delay_percent != null) {
      return `${label}がやや遅れています（遅れ度${Math.round(
        status.delay_percent
      )}%）。`;
    }
    if (status.delay_days != null) {
      return `${label}がやや遅れています（${status.delay_days}日遅れ）。`;
    }
    return `${label}がやや遅れています。`;
  }

  return `${label}は基準内です。`;
}

export default function StudentDetail({ student, groupMeta }) {
  if (!student) {
    return (
      <div className="student-detail empty">
        学生を選択してください
      </div>
    );
  }

  // Compute baseline actual dates using academic_year_start and baseline relative days
  const getBaselineDate = (relDay) => {
    if (groupMeta && relDay != null && groupMeta.academic_year_start) {
      const y = groupMeta.academic_year_start;
      // April 1 of academic year start
      const date = new Date(y, 3, 1);
      // add relative days
      date.setDate(date.getDate() + relDay);
      return date.toISOString().slice(0, 10);
    }
    return null;
  };

  const baselineBriefDate = getBaselineDate(student.baseline_briefing_rel_day);
  const baselineInterDate = getBaselineDate(student.baseline_interview_rel_day);

  return (
    <div className="student-detail">
      <h3>{student.user_name}</h3>

      <div className="section">
        <h4>基本情報</h4>
        <p>学籍番号：{student.user_no}</p>
        <p>学科：{student.course_class}</p>
      </div>

      <div className="section">
        <h4>現在の状況</h4>

        <div className="status-block">
          <strong>説明会</strong>
          <p>{explain(student.briefing_status, "説明会")}</p>
          <ul style={{ marginLeft: 16 }}>
            <li>
              基準相対日: {student.baseline_briefing_rel_day != null ? student.baseline_briefing_rel_day : "-"}
            </li>
            <li>
              基準開始日: {baselineBriefDate ? baselineBriefDate : "-"}
            </li>
            <li>
              初回実施日: {student.briefing_first_date ? student.briefing_first_date : "未実施"}
            </li>
            <li>
              遅延日数: {student.briefing_delay_days != null ? `${student.briefing_delay_days}日` : "-"}
            </li>
            <li>
              遅延率: {student.briefing_delay_percent != null ? `${Math.round(student.briefing_delay_percent)}%` : "-"}
            </li>
          </ul>
        </div>

        <div className="status-block">
          <strong>面接</strong>
          <p>{explain(student.interview_status, "面接")}</p>
          <ul style={{ marginLeft: 16 }}>
            <li>
              基準相対日: {student.baseline_interview_rel_day != null ? student.baseline_interview_rel_day : "-"}
            </li>
            <li>
              基準開始日: {baselineInterDate ? baselineInterDate : "-"}
            </li>
            <li>
              初回実施日: {student.interview_first_date ? student.interview_first_date : "未実施"}
            </li>
            <li>
              遅延日数: {student.interview_delay_days != null ? `${student.interview_delay_days}日` : "-"}
            </li>
            <li>
              遅延率: {student.interview_delay_percent != null ? `${Math.round(student.interview_delay_percent)}%` : "-"}
            </li>
          </ul>
        </div>
      </div>

      {groupMeta && (
        <div className="section meta">
          <h4>学科平均との差</h4>
          <p>
            学科の基準開始日（説明会）： {baselineBriefDate ? baselineBriefDate : "未算出"}
          </p>
          <p>
            学科の基準開始日（面接）： {baselineInterDate ? baselineInterDate : "未算出"}
          </p>
        </div>
      )}
    </div>
  );
}
