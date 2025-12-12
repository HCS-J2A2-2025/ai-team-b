import { useState } from "react";
import { useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";

export default function Result() {
  const location = useLocation();

  const initialCompanyName =
    location.state?.companyName || "会社名が入力されてません";
  const initialReport = location.state?.report || "";

  const [fixedCompanyName] = useState(initialCompanyName);
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
      setReport(data.report || "");
    } catch (error) {
      setApiError("API 接続エラー：サーバーに接続できませんでした");
    } finally {
      setIsLoading(false);
    }
  };
  const styles = {
    container: {
      minHeight: "100vh",
      backgroundColor: "#f5f5f5",
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif',
    },
    mainContent: {
      maxWidth: "1400px",
      margin: "0 auto",
      padding: "24px 16px 40px",
    },
    searchArea: {
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: "12px",
      marginBottom: "32px",
    },
    searchForm: {
      width: "100%",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: "16px",
    },
    searchInputRow: {
      width: "100%",
      display: "flex",
      justifyContent: "center",
      gap: "60px",
      flexWrap: "nowrap", // 横並び固定
      alignItems: "flex-start", // 上揃えにする
      boxSizing: "border-box",
    },

    // 入力欄＋候補リスト
    searchWrapper: {
      // 統一された幅：Search.jsx のデザインに合わせて広げる
      width: "min(820px, 95vw)",
      display: "flex",
      flexDirection: "column",
      boxSizing: "border-box",
    },

    searchInputWrapper: {
      // 検索バーの角丸やパディング、枠線を Search.jsx と同じにする
      width: "100%",
      borderRadius: "24px",
      border: "1px solid #dcdcdc",
      padding: "10px 24px",
      display: "flex",
      alignItems: "center",
      gap: "10px",
      backgroundColor: "#ffffff",
      boxSizing: "border-box",
    },
    searchInputWrapperHasSuggest: {
      borderBottomLeftRadius: 0,
      borderBottomRightRadius: 0,
    },

    // 予測候補
    suggestPanel: {
      width: "100%",
      marginTop: "0px",
      backgroundColor: "#ffffff",
      borderRadius: "0 0 24px 24px",
      border: "1px solid #e0e0e0",
      borderTop: "none",
      boxShadow: "0 4px 12px rgba(0,0,0,0.18)",
      overflow: "hidden",
      maxHeight: "320px",
      display: "flex",
      flexDirection: "column",
      zIndex: 1,
      boxSizing: "border-box",
    },
    // サジェスト行・ローディングのスタイルを追加
    suggestLoading: {
      padding: "8px 20px",
      fontSize: "12px",
      color: "#777",
    },
    suggestRow: {
      display: "flex",
      alignItems: "center",
      padding: "10px 20px",
      gap: "12px",
      fontSize: "14px",
      cursor: "pointer",
    },
    suggestIcon: {
      fontSize: "12px",
      color: "#8a8a8a",
    },
    suggestText: {
      flex: 1,
      color: "#202124",
    },
    searchIcon: {
      fontSize: "18px",
      color: "#aaaaaa",
    },
    searchInput: {
      flex: 1,
      border: "none",
      outline: "none",
      fontSize: "18px",
      fontWeight: 600,
      color: "#555555",
      background: "transparent",
    },
    searchButton: {
      // ボタン幅は Search.jsx に合わせて少し広めに
      minWidth: "160px",
      padding: "10px 40px",
      borderRadius: "999px",
      border: "1px solid #00b400",
      backgroundColor: "#11ff11",
      fontSize: "18px",
      fontWeight: 400,
      letterSpacing: "0.3em",
      color: "#ffffff",
      cursor: "pointer",
      boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
      whiteSpace: "nowrap",
      opacity: isLoading ? 0.7 : 1,
    },
    searchMetaText: {
      width: "100%",
      maxWidth: "960px",
      fontSize: "14px",
      color: "#555",
      textAlign: "left",
    },
    contentGrid: {
      display: "flex",
      flexWrap: "wrap",
      gap: "30px",
      alignItems: "stretch",
    },
    card: {
      background: "white",
      borderRadius: "12px",
      padding: "30px",
      boxShadow: "0 2px 10px rgba(0, 0, 0, 0.08)",
      border: "1px solid #e8e8e8",
      flex: "1 1 320px",
      minWidth: "280px",
      maxWidth: "100%",
    },
    aiReportHeader: {
      display: "flex",
      alignItems: "center",
      gap: "10px",
      marginBottom: "30px",
      paddingBottom: "15px",
      borderBottom: "2px solid #f0f0f0",
    },
    aiIcon: {
      fontSize: "24px",
    },
    aiReportTitle: {
      fontSize: "20px",
      fontWeight: 700,
      color: "#8b5cf6",
      margin: 0,
    },
    reportBody: {
      fontSize: "14px",
      lineHeight: 1.7,
      color: "#555",
      whiteSpace: "pre-wrap",
    },
    examRecordsTitle: {
      fontSize: "18px",
      fontWeight: 700,
      color: "#333",
      marginBottom: "20px",
    },
    recordsList: {
      display: "flex",
      flexDirection: "column",
      gap: "15px",
    },
    recordItem: {
      border: "1px solid #e0e0e0",
      borderRadius: "8px",
      overflow: "hidden",
      transition: "all 0.2s ease",
    },
    recordButton: {
      width: "100%",
      padding: "18px 20px",
      background: "white",
      border: "none",
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      transition: "background-color 0.2s ease",
      fontFamily: "inherit",
    },
    recordInfo: {
      display: "flex",
      alignItems: "center",
      gap: "15px",
      flexWrap: "wrap",
    },
    recordTitle: {
      fontSize: "15px",
      fontWeight: 700,
      color: "#333",
    },
    recordMeta: {
      fontSize: "13px",
      color: "#666",
    },
    recordStatus: {
      padding: "4px 12px",
      backgroundColor: "#d4f4dd",
      color: "#2d7f3e",
      fontSize: "12px",
      fontWeight: 600,
      borderRadius: "12px",
    },
    chevronIcon: {
      width: "20px",
      height: "20px",
      color: "#999",
      transition: "transform 0.3s ease",
      flexShrink: 0,
    },
    chevronRotated: {
      transform: "rotate(180deg)",
    },
    recordDetail: {
      padding: "20px",
      backgroundColor: "#f9f9f9",
      borderTop: "1px solid #e8e8e8",
      fontSize: "13px",
      color: "#666",
      lineHeight: 1.6,
    },
  };

  return (
    <>
      {/* モバイル幅ではボタンを下に表示し全幅にするレスポンシブCSS */}
      <style>{`
        @media (max-width: 750px) {
          .result-search-row {
            flex-direction: column;
            align-items: stretch;
            gap: 12px;
          }
          .result-search-button {
            width: 100%;
          }
        }
        .loading-spinner {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          border: 4px solid #e0e0e0;
          border-top-color: #1a73e8; /* 青いリング */
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    <div style={styles.container}>
      <AppHeader title="JobNavi Inteligens" onLogout={handleLogout} />

      <main style={styles.mainContent}>
        {isLoading && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(0,0,0,0.35)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
            }}
          >
            <div
              style={{
                minWidth: "260px",
                maxWidth: "80vw",
                padding: "24px 32px",
                borderRadius: "16px",
                backgroundColor: "#ffffff",
                boxShadow: "0 6px 16px rgba(0, 0, 0, 0.25)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "16px",
                fontSize: "16px",
                color: "#333",
                fontWeight: 700,
                letterSpacing: "0.03em",
              }}
            >
              <div>AI要約レポートを再生成中です…</div>
              <div className="loading-spinner"></div>
            </div>
          </div>
        )}
        {/* 再検索エリア */}
        <section style={styles.searchArea}>
          <form style={styles.searchForm} onSubmit={handleSearchSubmit}>
            <div style={styles.searchInputRow}
                className="result-search-row">
              {/* 入力＋候補 */}
              <div style={styles.searchWrapper}>
                <div
                  style={{
                    ...styles.searchInputWrapper,
                    borderRadius:
                      suggestions.length > 0
                        ? "24px 24px 0 0" // 上だけ角丸
                        : "24px",         // 全部角丸
                  }}
                >
                  <span style={styles.searchIcon}>🔍</span>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={handleSearchInputChange}
                    placeholder="会社名を記入　例）ダイアモンドヘッド"
                    style={styles.searchInput}
                  />
                </div>

                {(suggestions.length > 0) && (
                  <div style={styles.suggestPanel}>
                    {isSuggestLoading && (
                      <div style={styles.suggestLoading}>検索中...</div>
                    )}
                    {suggestions.map((name) => (
                      <div
                        key={name}
                        style={styles.suggestRow}
                        onClick={() => handleSuggestionClick(name)}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = "#f8f9fa";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = "#ffffff";
                        }}
                      >
                        <span style={styles.suggestIcon}>⏺</span>
                        <span style={styles.suggestText}>{name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <button type="submit" 
                      style={styles.searchButton}
                      className="result-search-button"
              >
                {isLoading ? "検索中..." : "検　索"}
              </button>
            </div>
          </form>
          {apiError && (
            <div style={{ marginBottom: "16px", color: "#d32f2f", fontSize: "14px" }}>
              {apiError}
            </div>
          )}
        </section>
        {/* 結果カード */}
        <div style={styles.contentGrid}>
          {/* 左カラム - AI要約レポート */}
          <div style={styles.card}>
            <div style={styles.aiReportHeader}>
              <span style={styles.aiIcon}>✨</span>
              <h3 style={styles.aiReportTitle}>
                AI要約レポート（{fixedCompanyName}）
              </h3>
            </div>

            <p style={styles.reportBody}>
              {report || "レポートがまだ取得されていません。検索してください。"}
            </p>
          </div>

          {/* 右カラム - 受験記録一覧（ダミー） */}
          <div style={styles.card}>
            <h3 style={styles.examRecordsTitle}>
              受験記録一覧({examRecords.length}件)
            </h3>

            <div style={styles.recordsList}>
              {examRecords.map((record) => (
                <div key={record.id} style={styles.recordItem}>
                  <button
                    type="button"
                    onClick={() => toggleExpand(record.id)}
                    style={styles.recordButton}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = "#fafafa";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = "white";
                    }}
                  >
                    <div style={styles.recordInfo}>
                      <span style={styles.recordTitle}>{record.title}</span>
                      <span style={styles.recordMeta}>{record.year}</span>
                      <span style={styles.recordMeta}>{record.term}</span>
                      <span style={styles.recordStatus}>{record.status}</span>
                      <span style={styles.recordMeta}>{record.type}</span>
                    </div>
                    <svg
                      style={{
                        ...styles.chevronIcon,
                        ...(expandedItem === record.id
                          ? styles.chevronRotated
                          : {}),
                      }}
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
                    <div style={styles.recordDetail}>
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