import { useState } from "react";
import { useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import '../css/Result.css';

export default function Result() {
  const location = useLocation();

  const initialCompanyName =
    location.state?.companyName || "会社名が入力されてません";
  const initialReport = location.state?.report || "";

  const [fixedCompanyName, setFixedCompanyName] = useState(initialCompanyName);
  const [expandedItem, setExpandedItem] = useState(null);
  const [searchQuery, setSearchQuery] = useState(initialCompanyName);
  const [report, setReport] = useState(initialReport);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [isSuggestLoading, setIsSuggestLoading] = useState(false);
  const [apiError, setApiError] = useState(null);

  const examRecords = [
    {
      id: 1,
      title: "一次面接",
      year: "2024年",
      term: "学部4年",
      status: "合格",
      type: "オンライン",
    },
    {
      id: 2,
      title: "二次面接",
      year: "2024年",
      term: "学部3年",
      status: "合格",
      type: "対面",
    },
    {
      id: 3,
      title: "最終面接",
      year: "2023年",
      term: "学部4年",
      status: "合格",
      type: "オンライン",
    },
  ];

  const toggleExpand = (id) => {
    setExpandedItem(expandedItem === id ? null : id);
  };

  const handleLogout = () => {
    console.log("ログアウトしました");
  };

  // 再検索 => POST /company
  const handleSearchInputChange = async (e) => {
    const value = e.target.value;
    setSearchQuery(value);

    if (!value) {
      setSuggestions([]);
      return;
    }
    setIsSuggestLoading(true);
    try {
      const res = await fetch("http://localhost:8000/company_suggest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ keyword: value }),
      });

      if (!res.ok) {
        console.error("候補取得に失敗しました", res.status);
        setSuggestions([]);
        return;
      }

      const data = await res.json();
      setSuggestions(data.candidates || []);
    } catch (err) {
      console.error("候補取得エラー:", err);
      setSuggestions([]);
    } finally {
      setIsSuggestLoading(false);
    }
  };
  // ▼ 候補クリックで検索欄に反映
  const handleSuggestionClick = (name) => {
    setSearchQuery(name);
    setSuggestions([]);
  };

  // 再検索 => POST /company
  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim() || isLoading) return;

    setIsLoading(true);
    setApiError(null);
    setReport("");
    try {
      const res = await fetch("http://localhost:8000/company", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: searchQuery }),
      });
      if (!res.ok) {
        setApiError(`AI要約レポートの再生成に失敗しました（HTTP ${res.status}）`);
        return;
      }
      const data = await res.json();

      if (data.error) {
        setApiError(data.error || "企業が見つかりません");
        return;
      }
      const searchedName = searchQuery.trim();
      setFixedCompanyName(searchedName);
      setReport(data.report || "");
    } catch (error) {
      setApiError("API 接続エラー：サーバーに接続できませんでした");
    } finally {
      setIsLoading(false);
    }
  };
  // Determine dynamic classes based on component state
  const searchInputWrapperClass =
    suggestions.length > 0
      ? "result-search-input-wrapper result-search-input-wrapper-has-suggest"
      : "result-search-input-wrapper";

  const searchButtonClass = isLoading
    ? "result-search-button result-search-button-loading"
    : "result-search-button";

  return (
    <>
      <div className="result-container">
        <AppHeader title="JobNavi Inteligens" onLogout={handleLogout} />

        <main className="result-main-content">
          {isLoading && (
            <div className="result-overlay">
              <div className="result-loading-box">
                <div>AI要約レポートを再生成中です…</div>
                <div className="loading-spinner"></div>
              </div>
            </div>
          )}
          {/* 再検索エリア */}
          <section className="result-search-area">
            <form className="result-search-form" onSubmit={handleSearchSubmit}>
              <div className={`result-search-input-row result-search-row`}>
                {/* 入力＋候補 */}
                <div className="result-search-wrapper">
                  <div className={searchInputWrapperClass}>
                    <span className="result-search-icon">🔍</span>
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={handleSearchInputChange}
                      placeholder="会社名を記入　例）ダイアモンドヘッド"
                      className="result-search-input"
                    />
                  </div>

                  {suggestions.length > 0 && (
                    <div className="result-suggest-panel">
                      {isSuggestLoading && (
                        <div className="result-suggest-loading">検索中...</div>
                      )}
                      {suggestions.map((name) => (
                        <div
                          key={name}
                          className="result-suggest-row"
                          onClick={() => handleSuggestionClick(name)}
                        >
                          <span className="result-suggest-icon">⏺</span>
                          <span className="result-suggest-text">{name}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <button type="submit" className={searchButtonClass}>
                  {isLoading ? "検索中..." : "検　索"}
                </button>
              </div>
            </form>
            {apiError && (
              <div className="result-api-error">
                {apiError}
              </div>
            )}
          </section>
          {/* 結果カード */}
          <div className="result-content-grid">
            {/* 左カラム - AI要約レポート */}
            <div className="result-card">
              <div className="result-ai-report-header">
                <span className="result-ai-icon">✨</span>
                <h3 className="result-ai-report-title">
                  {isLoading
                  ? `AI要約レポート（${searchQuery.trim()}）`
                  : `AI要約レポート（${fixedCompanyName}）`}
                </h3>
              </div>

              <p className="result-report-body">
                {report || "レポートがまだ取得されていません。しばらくお待ちください。"}
              </p>
            </div>

            {/* 右カラム - 受験記録一覧（ダミー） */}
            <div className="result-card">
              <h3 className="result-exam-records-title">
                受験記録一覧({examRecords.length}件)
              </h3>

              <div className="result-records-list">
                {examRecords.map((record) => (
                  <div key={record.id} className="result-record-item">
                    <button
                      type="button"
                      onClick={() => toggleExpand(record.id)}
                      className="result-record-button"
                    >
                      <div className="result-record-info">
                        <span className="result-record-title">{record.title}</span>
                        <span className="result-record-meta">{record.year}</span>
                        <span className="result-record-meta">{record.term}</span>
                        <span className="result-record-status">{record.status}</span>
                        <span className="result-record-meta">{record.type}</span>
                      </div>
                      <svg
                        className={expandedItem === record.id ? `result-chevron-icon result-chevron-rotated` : `result-chevron-icon`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </button>

                    {expandedItem === record.id && (
                      <div className="result-record-detail">
                        <p>詳細な面接内容や質問事項がここに表示されます。</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  );
}
