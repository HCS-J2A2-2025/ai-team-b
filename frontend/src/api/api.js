const fetchCompanyReport = async (companyName) => {
  const name = (companyName || "").trim();
  if (!name) return;

  setIsLoading(true);
  setApiError(null);
  setExpandedItem(null);

  setDetailsMap({});
  setDetailLoadingMap({});
  setDetailErrorMap({});

  try {
    // ① POST：request_id だけ返る
    const res = await fetch("http://localhost:8000/api/company/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });

    const postData = await res.json();

    if (!res.ok || postData?.error) {
      setReport("");
      setRecords([]);
      setApiError(postData?.error || `取得に失敗しました（HTTP ${res.status}）`);
      return;
    }

    const requestId = postData?.request_id;
    if (!requestId) {
      setReport("");
      setRecords([]);
      setApiError("request_id が返ってきませんでした");
      return;
    }

    // ② GET：本体データ取得
    const res2 = await fetch(
      `http://localhost:8000/api/company/report/result?request_id=${encodeURIComponent(
        requestId
      )}`
    );

    const data = await res2.json();

    if (!res2.ok || data?.error) {
      setReport("");
      setRecords([]);
      setApiError(data?.error || `取得に失敗しました（HTTP ${res2.status}）`);
      return;
    }

    // ③ 画面反映
    setFixedCompanyName(name);
    setReport(data.report || "");

    const all = Array.isArray(data.interviews) ? data.interviews : [];
    setRecords(all.slice(-10));
  } catch (e) {
    setReport("");
    setRecords([]);
    setApiError("API 接続エラー");
  } finally {
    setIsLoading(false);
  }
};
