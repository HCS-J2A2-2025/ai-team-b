// Result.jsx
import { useState } from 'react';
import { useLocation } from "react-router-dom";
import AppHeader from './AppHeader';

export default function Result() {
  const location = useLocation();
  const companyName = location.state?.companyName || "会社名が入力されてません";

  const [expandedItem, setExpandedItem] = useState(null);
  const [searchQuery, setSearchQuery] = useState(companyName);

  const examRecords = [
    {
      id: 1,
      title: '一次面接',
      year: '2024年',
      term: '学部4年',
      status: '合格',
      type: 'オンライン',
    },
    {
      id: 2,
      title: '二次面接',
      year: '2024年',
      term: '学部3年',
      status: '合格',
      type: '対面',
    },
    {
      id: 3,
      title: '最終面接',
      year: '2023年',
      term: '学部4年',
      status: '合格',
      type: 'オンライン',
    },
  ];

  const toggleExpand = (id) => {
    setExpandedItem(expandedItem === id ? null : id);
  };

  const handleLogout = () => {
    console.log('ログアウトしました');
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    console.log('再検索:', searchQuery);
  };

  const styles = {
    container: {
      minHeight: '100vh',
      backgroundColor: '#f5f5f5',
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif',
    },

    mainContent: {
      maxWidth: '1400px',
      margin: '0 auto',
      padding: '24px 16px 40px',
    },

    /* ─── 再検索エリア ─── */
    searchArea: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '12px',
      marginBottom: '32px',
    },
    searchForm: {
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '16px',
    },
    searchInputRow: {
      width: '100%',
      display: 'flex',
      justifyContent: 'center',
      gap: '12px',
      flexWrap: 'wrap',
    },
    searchInputWrapper: {
      width: 'min(620px, 95vw)',
      borderRadius: '999px',
      border: '1px solid #cfcfcf',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      backgroundColor: '#ffffff',
    },
    searchIcon: {
      fontSize: '18px',
      color: '#aaaaaa',
    },
    searchInput: {
      flex: 1,
      border: 'none',
      outline: 'none',
      fontSize: '16px',
      fontWeight: 600,
      color: '#333',
      background: 'transparent',
    },
    searchButton: {
      minWidth: '140px',
      padding: '10px 32px',
      borderRadius: '999px',
      border: '1px solid #00b400',
      backgroundColor: '#11ff11',
      fontSize: '16px',
      fontWeight: 400,
      letterSpacing: '0.3em',
      color: '#ffffff',
      cursor: 'pointer',
      boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
      whiteSpace: 'nowrap',
    },
    searchMetaText: {
      width: '100%',
      maxWidth: '960px',
      fontSize: '14px',
      color: '#555',
      textAlign: 'left',
    },

    /* ─── 結果カード ─── */
    contentGrid: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: '30px',
      alignItems: 'stretch',
    },
    card: {
      background: 'white',
      borderRadius: '12px',
      padding: '30px',
      boxShadow: '0 2px 10px rgba(0, 0, 0, 0.08)',
      border: '1px solid #e8e8e8',
      flex: '1 1 320px',
      minWidth: '280px',
      maxWidth: '100%',
    },
    aiReportHeader: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      marginBottom: '30px',
      paddingBottom: '15px',
      borderBottom: '2px solid #f0f0f0',
    },
    aiIcon: {
      fontSize: '24px',
    },
    aiReportTitle: {
      fontSize: '20px',
      fontWeight: 700,
      color: '#8b5cf6',
      margin: 0,
    },
    reportSection: {
      marginBottom: '25px',
    },
    sectionHeader: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      marginBottom: '12px',
    },
    sectionIcon: {
      fontSize: '20px',
    },
    sectionTitle: {
      fontSize: '16px',
      fontWeight: 700,
      color: '#333',
      margin: 0,
    },
    sectionContent: {
      paddingLeft: '35px',
      fontSize: '14px',
      lineHeight: 1.7,
      color: '#555',
      margin: 0,
    },
    sectionList: {
      listStyle: 'none',
      paddingLeft: '35px',
      margin: 0,
    },
    listItem: {
      fontSize: '14px',
      lineHeight: 1.8,
      color: '#555',
      marginBottom: '6px',
    },

    examRecordsTitle: {
      fontSize: '18px',
      fontWeight: 700,
      color: '#333',
      marginBottom: '20px',
    },
    recordsList: {
      display: 'flex',
      flexDirection: 'column',
      gap: '15px',
    },
    recordItem: {
      border: '1px solid #e0e0e0',
      borderRadius: '8px',
      overflow: 'hidden',
      transition: 'all 0.2s ease',
    },
    recordButton: {
      width: '100%',
      padding: '18px 20px',
      background: 'white',
      border: 'none',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      transition: 'background-color 0.2s ease',
      fontFamily: 'inherit',
    },
    recordInfo: {
      display: 'flex',
      alignItems: 'center',
      gap: '15px',
      flexWrap: 'wrap',
    },
    recordTitle: {
      fontSize: '15px',
      fontWeight: 700,
      color: '#333',
    },
    recordMeta: {
      fontSize: '13px',
      color: '#666',
    },
    recordStatus: {
      padding: '4px 12px',
      backgroundColor: '#d4f4dd',
      color: '#2d7f3e',
      fontSize: '12px',
      fontWeight: 600,
      borderRadius: '12px',
    },
    chevronIcon: {
      width: '20px',
      height: '20px',
      color: '#999',
      transition: 'transform 0.3s ease',
      flexShrink: 0,
    },
    chevronRotated: {
      transform: 'rotate(180deg)',
    },
    recordDetail: {
      padding: '20px',
      backgroundColor: '#f9f9f9',
      borderTop: '1px solid #e8e8e8',
      fontSize: '13px',
      color: '#666',
      lineHeight: 1.6,
    },
  };

  return (
    <div style={styles.container}>
      {/* 共通ヘッダー */}
      <AppHeader title="JobNavi Inteligens" onLogout={handleLogout} />

      {/* メインコンテンツ */}
      <main style={styles.mainContent}>
        {/* 再検索エリア（Google 風） */}
        <section style={styles.searchArea}>
          <form style={styles.searchForm} onSubmit={handleSearchSubmit}>
            <div style={styles.searchInputRow}>
              <div style={styles.searchInputWrapper}>
                <span style={styles.searchIcon}>🔍</span>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="会社名を記入　例）ダイアモンドヘッド"
                  style={styles.searchInput}
                />
              </div>

              <button type="submit" style={styles.searchButton}>
                検　索
              </button>
            </div>
          </form>

          <p style={styles.searchMetaText}>
            {searchQuery} の情報　検索結果: {examRecords.length}件
          </p>
        </section>

        {/* 結果カード */}
        <div style={styles.contentGrid}>
          {/* 左カラム - AI要約レポート */}
          <div style={styles.card}>
            <div style={styles.aiReportHeader}>
              <span style={styles.aiIcon}>✨</span>
              <h3 style={styles.aiReportTitle}>AI要約レポート</h3>
            </div>

            {/* 雰囲気 */}
            <div style={styles.reportSection}>
              <div style={styles.sectionHeader}>
                <span style={styles.sectionIcon}>🧠</span>
                <h4 style={styles.sectionTitle}>雰囲気</h4>
              </div>
              <p style={styles.sectionContent}>
                温かく和やかな雰囲気、面接官は話をよく聞いてくれる傾向。学生の意見を尊重し、対話形式で進むことが多い。
              </p>
            </div>

            {/* よく聞かれる質問 */}
            <div style={styles.reportSection}>
              <div style={styles.sectionHeader}>
                <span style={styles.sectionIcon}>❓</span>
                <h4 style={styles.sectionTitle}>よく聞かれる質問</h4>
              </div>
              <ul style={styles.sectionList}>
                <li style={styles.listItem}>• 学生時代に力を入れたこと（ガクチカ）</li>
                <li style={styles.listItem}>• なぜ事業を志望するのか</li>
                <li style={styles.listItem}>• チームでの役割や論番経験</li>
                <li style={styles.listItem}>• 入社後にやりたいこと</li>
              </ul>
            </div>

            {/* 服装 */}
            <div style={styles.reportSection}>
              <div style={styles.sectionHeader}>
                <span style={styles.sectionIcon}>👔</span>
                <h4 style={styles.sectionTitle}>服装</h4>
              </div>
              <p style={styles.sectionContent}>
                スーツ着用が基本。一部オンライン面接では「オフィスカジュアル可」との記載あり。
              </p>
            </div>

            {/* 面接形式 */}
            <div style={styles.reportSection}>
              <div style={styles.sectionHeader}>
                <span style={styles.sectionIcon}>💼</span>
                <h4 style={styles.sectionTitle}>面接形式</h4>
              </div>
              <p style={styles.sectionContent}>
                おおむね面接官2名、学生側は1名もしくは2名で実施されている。
              </p>
            </div>
          </div>

          {/* 右カラム - 受験記録一覧 */}
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
                      e.currentTarget.style.backgroundColor = '#fafafa';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'white';
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
  );
}
