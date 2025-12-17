const fetchCompanyReport = async (companyName) => {
  const name = (companyName || "").trim();
  if (!name) return;

  // UI初期化
  setIsLoading(true);
  setApiError(null);
  setExpandedItem(null);
  setDetailsMap({});
  setDetailLoadingMap({});
  setDetailErrorMap({});

  // 連打や画面遷移で前の通信を止められるように
  const controller = new AbortController();
  const signal = controller.signal;

  // もし前回のcontrollerを保持してるなら止める（任意）
  // if (abortRef.current) abortRef.current.abort();
  // abortRef.current = controller;

  // タイムアウト（長い要約でも耐えるように少し長め）
  const withTimeout = (ms) => {
    const t = setTimeout(() => controller.abort(), ms);
    return () => clearTimeout(t);
  };

  const BASE = "http://localhost:8000";

  const safeJson = async (res) => {
    // JSONじゃない(HTMLエラー等)ケースでも落ちない
    const text = await res.text();
    try {
      return text ? JSON.parse(text) : {};
    } catch {
      return { error: text || `HTTP ${res.status}` };
    }
  };

  const normalizeError = (res, data) => {
    if (data?.error) return data.error;
    if (!res.ok) return `取得に失敗しました（HTTP ${res.status}）`;
    return null;
  };

  try {
    // ① request_id を取得
    const clear1 = withTimeout(30_000); // 30秒
    const res = await fetch(`${BASE}/api/company/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
      signal,
    });
    clear1();

    const postData = await safeJson(res);
    const err1 = normalizeError(res, postData);
    if (err1) {
      setReport("");
      setRecords([]);
      setApiError(err1);
      return;
    }

    const requestId = postData?.request_id;
    if (!requestId) {
      setReport("");
      setRecords([]);
      setApiError("request_id が返ってきませんでした");
      return;
    }

    // ② 本体データ取得（あなたのバックは POST が正）
    // ※要約が重いならここは長めに
    const clear2 = withTimeout(600_000); // 10分
    const res2 = await fetch(`${BASE}/api/company/report/result`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId }),
      signal,
    });
    clear2();

    const data = await safeJson(res2);
    const err2 = normalizeError(res2, data);
    if (err2) {
      setReport("");
      setRecords([]);
      setApiError(err2);
      return;
    }

    // ③ 画面反映
    setFixedCompanyName(data.company || name);
    setReport(data.report || "");

    // バックは records を返す（interviews ではない）
    const recs = Array.isArray(data.records) ? data.records : [];
    setRecords(recs); // バックが 4枚に整形してるならそのまま出すのが正解
  } catch (e) {
    // Abort(中断)はエラー表示しない/軽くするのが自然
    if (e?.name === "AbortError") return;

    setReport("");
    setRecords([]);
    setApiError("API 接続エラー");
  } finally {
    setIsLoading(false);
  }
};
