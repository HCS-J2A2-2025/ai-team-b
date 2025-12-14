export function phaseLabel(status) {
  if (!status) return "不明";
  if (status.status === "not_started") return "未開始";

  switch (status.level) {
    case "danger":
      return "要対応";
    case "warn":
      return "注意";
    case "ok":
      return "問題なし";
    default:
      return "不明";
  }
}

export function phaseColor(status) {
  if (!status) return "#999";
  if (status.status === "not_started") return "#d32f2f"; // 赤

  switch (status.level) {
    case "danger":
      return "#d32f2f";
    case "warn":
      return "#f9a825";
    case "ok":
      return "#2e7d32";
    default:
      return "#999";
  }
}
