    // Search.jsx
    import { useState, useRef , useEffect } from 'react';
    import AppHeader from './AppHeader';
    import { useNavigate } from "react-router-dom";

    export default function Search() {
    const [company, setCompany] = useState('');
    const [selectedFile, setSelectedFile] = useState(null); // 選択中CSV
    const [isDragOver, setIsDragOver] = useState(false);    // ドラッグ中か
    const [role, setRole] = useState(null);
    const fileInputRef = useRef(null);
    const navigate = useNavigate();

  // マウント時に ログイン情報を取得
    useEffect(() => {
    const stored = localStorage.getItem("jobnaviUser");
    if (!stored) {
        // 未ログイン → ログインページに戻す
        navigate("/");
        return;
    }
    try {
        const user = JSON.parse(stored);
        setRole(user.role); // "student" / "teacher" / "admin"
    } catch (e) {
        console.error(e);
        navigate("/");
    }
    }, [navigate]);

    // 検索ボタン押したときに /result へ遷移 + 会社名を渡す
    const handleSubmit = (e) => {
    e.preventDefault();
    navigate("/result", {
        state: { companyName: company }
    });
    };

    const handleLogout = () => {
    console.log('ログアウトしました');
    };

    // 「参照」ボタン / input change
    const handleFileChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    setSelectedFile(file);
    console.log("選択されたファイル:", file.name);
    // ここで実際のアップロード処理(API呼び出しなど)を実装
    };

    const handleBrowseClick = () => {
    if (fileInputRef.current) {
        fileInputRef.current.click();
    }
    };

    // ドラッグ & ドロップ
    const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
    };

    const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    };

    const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!file) return;
    setSelectedFile(file);
    console.log("ドロップされたファイル:", file.name);
    // ここでアップロード処理を呼び出してもよい
    };

    return (
    <>
        <style>{`
        html, body, #root {
            height: 100%;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
            font-weight: 600; /* 全体を太字（検索以外） */
        }

        .app-root {
            min-height: 100vh;
            background-color: #ffffff;
            display: flex;
            flex-direction: column;
        }

        /* ───────── コンテンツ ───────── */

        .app-main {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px 0 80px;
            gap: 40px; /* 検索とアップロードの間隔 */
        }

        .main-title {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 40px;
        }

        .search-area {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 24px;
        }

        .search-input-wrapper {
            width: min(720px, 95vw);
            border-radius: 999px;
            border: 1px solid #999;
            padding: 10px 24px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .search-icon {
            font-size: 18px;
            color: #aaaaaa;
        }

        .search-input {
            flex: 1;
            border: none;
            outline: none;
            font-size: 18px;
            color: #555555;
            font-weight: 600;
            background: transparent;
        }

        .search-input::placeholder {
            color: #c4c4c4;
            font-weight: 400;
        }

        /* 「検索」だけ太字にしない */
        .search-button {
            min-width: 160px;
            padding: 10px 40px;
            border-radius: 999px;
            border: 1px solid #00b400;
            background-color: #11ff11;
            font-size: 18px;
            font-weight: 400;
            letter-spacing: 0.4em;
            color: #ffffff;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        .search-button:active {
            transform: scale(0.95);
        }

        /* ───────── CSVアップロード欄 ───────── */

        .upload-section {
            width: min(720px, 95vw);
            display: flex;
            flex-direction: column;
            align-items: stretch;
        }

        .upload-title {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 12px;
        }

        .upload-box {
            padding: 40px 16px 32px;
            border-radius: 16px;
            border: 2px dashed #c4c4c4;
            background-color: #fafafa;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
            text-align: center;
            transition: background-color 0.2s ease, border-color 0.2s ease;
        }

        .upload-box.drag-over {
            border-color: #1a73e8;
            background-color: #e8f0fe;
        }

        /* なんとなく雲っぽい形を再現（装飾用） */
        .upload-cloud {
            width: 120px;
            height: 70px;
            border-radius: 999px;
            background: #e0e0e0;
            position: relative;
        }

        .upload-cloud::before,
        .upload-cloud::after {
            content: "";
            position: absolute;
            border-radius: 999px;
            background: #e0e0e0;
        }

        .upload-cloud::before {
            width: 70px;
            height: 70px;
            top: -30px;
            left: 10px;
        }

        .upload-cloud::after {
            width: 90px;
            height: 90px;
            top: -40px;
            right: 0;
        }

        .upload-browse-button {
            padding: 10px 32px;
            border-radius: 999px;
            border: none;
            background-color: #1a73e8;
            color: #ffffff;
            font-size: 16px;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }

        .upload-browse-button:active {
            transform: scale(0.96);
        }

        .upload-help-text {
            font-size: 14px;
            color: #666666;
        }

        .upload-file-name {
            margin-top: 8px;
            font-size: 13px;
            color: #333333;
        }

        /* ───────── レスポンシブ（スマホ調整）───────── */

        @media (max-width: 768px) {
            .app-main {
            padding: 32px 0 64px;
            }

            .main-title {
            font-size: 26px;
            margin-bottom: 28px;
            text-align: center;
            }

            .search-input-wrapper {
            width: 94vw;
            padding: 10px 18px;
            }

            .search-input {
            font-size: 16px;
            }

            .search-button {
            width: 72vw;
            max-width: 320px;
            font-size: 16px;
            letter-spacing: 0.3em;
            }
        }

        @media (max-width: 480px) {
            .main-title {
            font-size: 22px;
            }

            .search-button {
            width: 80vw;
            }
        }
        `}</style>

        <div className="app-root">
        {/* 共通ヘッダー */}
        <AppHeader title="JobNavi Inteligens" onLogout={handleLogout} />

        <main className="app-main">
            {/* 検索機能 */}
            <section>
            <h1 className="main-title">JobNavi Inteligens</h1>

            <form className="search-area" onSubmit={handleSubmit}>
                <div className="search-input-wrapper">
                <span className="search-icon">🔍</span>

                <input
                    type="text"
                    className="search-input"
                    placeholder="会社名を記入　 例）ダイアモンドヘッド"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                />
                </div>

                <button type="submit" className="search-button">
                検　索
                </button>
            </form>
            </section>
            {role === "admin" && (//CSVアップロード欄（常に表示）
                <section className="upload-section">
                    <div className="upload-title">CSV一括登録（管理者用）</div>

                    <div
                        className={`upload-box ${isDragOver ? 'drag-over' : ''}`}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={handleBrowseClick} // 全体クリックでも参照
                    >
                        <div className="upload-cloud" />

                        <button
                        type="button"
                        className="upload-browse-button"
                        onClick={(e) => {
                            e.stopPropagation();
                            handleBrowseClick();
                        }}
                        >
                        参　照
                        </button>

                        <p className="upload-help-text">
                        CSVファイルをここにドラッグ＆ドロップするか、<br />
                        「参照」ボタンから選択してください。
                        </p>

                        {selectedFile && (
                        <div className="upload-file-name">
                            選択中のファイル：{selectedFile.name}
                        </div>
                        )}

                        {/* 実際の input は隠す */}
                        <input
                        type="file"
                        accept=".csv"
                        ref={fileInputRef}
                        style={{ display: 'none' }}
                        onChange={handleFileChange}
                        />
                    </div>
                </section>
            )}
        </main>
        </div>
    </>
    );
    }