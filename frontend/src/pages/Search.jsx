// Search.jsx
import { useState, useRef, useEffect } from 'react';
import AppHeader from '../components/AppHeader';
import { useNavigate } from "react-router-dom";
import '../css/Search.css';

export default function Search() {
    const [company, setCompany] = useState('');
    const [suggestions, setSuggestions] = useState([]);
    const [isSuggestLoading, setIsSuggestLoading] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null); // 選択中CSV
    const [isDragOver, setIsDragOver] = useState(false);    // ドラッグ中か
    const [role, setRole] = useState(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [showSubmitting, setShowSubmitting] = useState(false);
    const [apiError, setApiError] = useState(null);
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
    const handleSubmit = async (e) => {
    e.preventDefault();
    if (!company.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setApiError(null);

    let timerId = null;
    timerId = setTimeout(() => setShowSubmitting(true), 200); // ★200ms遅延

    try {
        const res = await fetch("http://localhost:8000/company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: company }),
        });

        if (!res.ok) {
        setApiError(`AI要約レポートの生成に失敗しました（HTTP ${res.status}）`);
        return;
        }

        const data = await res.json();
        if (data.error) {
        setApiError(data.error || "AI要約レポートの生成中にエラーが発生しました");
        return;
        }

        navigate("/result", {
        state: { companyName: company, report: data.report || "" },
        });
    } catch (error) {
        console.error(error);
        setApiError("API 接続エラー：サーバーに接続できませんでした");
    } finally {
        clearTimeout(timerId);
        setShowSubmitting(false);
        setIsSubmitting(false);
    }
    };


    const handleLogout = () => {
        console.log('ログアウトしました');
    };

    // アップロード用ボタン / input change
    const handleFileUpload = (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith(".csv")) {
            alert("CSV ファイルのみ選択できます");
            return;
        }
        setSelectedFile(file);
        console.log("選択されたファイル:", file.name);
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

    const removeSelectedFile = () => {
        setSelectedFile(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = ""; // input の中身リセット
        }
    };

    const handleCsvUpload = async (file) => {
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("http://localhost:8000/api/upload_csv", {
                method: "POST",
                body: formData,
            });

            const data = await res.json();

            if (data.status === "ok") {
                alert("CSV アップロード成功: " + data.filename);
            } else {
                alert("CSV アップロードエラー: " + data.message);
            }
        } catch (e) {
            alert("サーバーに接続できません（API エラー）");
        }
    };
    const handleCompanyChange = async (e) => {
        const value = e.target.value;
        setCompany(value);

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
    const handleSuggestionClick = (name) => {
        setCompany(name);
        setSuggestions([]);
    };

    return (
        <>
        <div className="app-root">
        {/* 共通ヘッダー */}
        <AppHeader title="JobNavi Inteligens" onLogout={handleLogout} />
        <main className="app-main">
            {showSubmitting && (
                <div className="loading-backdrop">
                    <div className="loading-box">
                        <div className="loading-text">
                            AI要約レポートを生成しています…
                        </div>
                        <div className="loading-spinner" />
                    </div>
                </div>
            )}
            {/* 検索機能 */}
            <section>
                <h1 className="main-title">JobNavi Inteligens</h1>

                <form className="search-area" onSubmit={handleSubmit}>
                    {/* 入力欄＋候補パネルをまとめる */}
                    <div className="search-wrapper">
                        <div
                            className={`search-input-wrapper ${suggestions.length > 0 ? "has-suggest" : ""
                                }`}
                        >
                            <span className="search-icon">🔍</span>

                            <input
                                type="text"
                                className="search-input"
                                placeholder="会社名を記入　 例）ダイアモンドヘッド"
                                value={company}
                                onChange={handleCompanyChange}
                            />
                        </div>

                        {suggestions.length > 0 && (
                            <div className="suggest-panel">
                                {isSuggestLoading && (
                                    <div className="suggest-loading">検索中...</div>
                                )}

                                {suggestions.map((name) => (
                                    <div
                                        key={name}
                                        className="suggest-row"
                                        onClick={() => handleSuggestionClick(name)}
                                    >
                                        <span className="suggest-icon">⏺</span>
                                        <span className="suggest-text">{name}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <button
                        type="submit"
                        className="search-button"
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? "検索中..." : "検　索"}
                    </button>
                </form>
                {apiError && (
                    <div style={{ marginTop: "16px", color: "#d32f2f", fontSize: "14px" }}>
                        {apiError}
                    </div>
                )}
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
                        <p className="upload-help-text">
                            CSVファイルをここにドラッグ＆ドロップする<br />
                        </p>
                        {selectedFile && (
                            <div className="upload-file-wrapper">
                                <span>{selectedFile.name}</span>
                                <button
                                    type="button"
                                    className="remove-file-button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeSelectedFile();
                                    }}
                                >
                                    ×
                                </button>
                            </div>
                        )}
                        {/* 実際の input は隠す */}
                        <input
                            type="file"
                            accept=".csv"
                            ref={fileInputRef}
                            style={{ display: 'none' }}
                            onChange={handleFileUpload}
                        />
                    </div>
                    <button
                        type="button"
                        className="upload-browse-button"
                        onClick={() => handleCsvUpload(selectedFile)}
                        disabled={!selectedFile}
                    >
                        アップロード
                    </button>
                </section>
            )}
        </main>
        </div>
        </>
    );
}
