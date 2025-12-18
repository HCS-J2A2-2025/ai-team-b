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
    const suggestAbortRef = useRef(null);
    const latestSuggestKeyRef = useRef("");   // 最後に投げたkeyword
    const suppressSuggestRef = useRef(false); // サジェスト確定クリック直後の“復活”を抑止
    const suggestSeqRef = useRef(0);       // 古いレスポンスを捨てる番号
    const composingRef = useRef(false);
    const pendingSelectRef = useRef(null);
    const inputRef = useRef(null);

    const applyPendingSelect = () => {
    if (pendingSelectRef.current) {
        handleSuggestionClick(pendingSelectRef.current);
        pendingSelectRef.current = null;
    }
    };


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
        return () => {
            if (suggestAbortRef.current) suggestAbortRef.current.abort();
        };
    }, [navigate]);

    // 検索ボタン押したときに /result へ遷移 + 会社名を渡す
    const handleSubmit = async (e) => {
    e.preventDefault();
    const raw = company.trim();
    if (!raw || isSubmitting) return;

    setIsSubmitting(true);
    setApiError(null);

    try {
        // ① まず存在チェック（AIなし）
        const vres = await fetch("http://localhost:8000/api/company/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: raw }),
        });

        const vjson = await vres.json().catch(() => ({}));
        if (!vres.ok || vjson?.ok === false) {
        setApiError(vjson?.error || `入力チェックに失敗しました（HTTP ${vres.status}）`);
        return;
        }

        // ② OKなら Resultへ遷移（ここでは生成しない）
        const canonicalName = vjson?.company || raw;
        navigate("/result", { state: { companyName: canonicalName } });
    } catch (err) {
        setApiError("API 接続エラー：サーバーに接続できませんでした");
    } finally {
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
    setApiError(null);

    // 確定クリック直後は走らせない（復活防止）
    if (suppressSuggestRef.current) return;

    const key = value.trim();

    // 空なら候補消す＆通信止める
    if (!key) {
        if (suggestAbortRef.current) suggestAbortRef.current.abort();
        setSuggestions([]);
        return;
    }

    // ★この入力に対するリクエスト番号
    const seq = ++suggestSeqRef.current;

    // 前回を中断
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    const controller = new AbortController();
    suggestAbortRef.current = controller;

    setIsSuggestLoading(true);

    try {
        const res = await fetch("http://localhost:8000/company_suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: value }),
        signal: controller.signal,
        });

        const data = await res.json().catch(() => ({}));

        // ★古い返りは捨てる（これが本命）
        if (seq !== suggestSeqRef.current) return;
        if (suppressSuggestRef.current) return;

        if (!res.ok) {
        setSuggestions([]);
        return;
        }

        setSuggestions(Array.isArray(data?.candidates) ? data.candidates : []);
    } catch (err) {
        if (err?.name !== "AbortError") console.error("候補取得エラー:", err);
        // ★古い返りは捨てる
        if (seq !== suggestSeqRef.current) return;
        setSuggestions([]);
    } finally {
        if (seq === suggestSeqRef.current) setIsSuggestLoading(false);
    }
    };



    const handleSuggestionClick = (name) => {
    suppressSuggestRef.current = true;

    // 進行中のサジェスト通信を止める
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    suggestSeqRef.current++; // ★これで「遅れて返ったやつ」は必ず捨てられる

    setCompany(name);
    setSuggestions([]);
    setApiError(null);
    setIsSuggestLoading(false);

    // 次にユーザーが入力したら再開
    setTimeout(() => {
        suppressSuggestRef.current = false;
    }, 0);
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
                                    ref={inputRef}
                                    type="text"
                                    className="search-input"
                                    placeholder="会社名を記入　 例）ダイアモンドヘッド"
                                    value={company}
                                    onChange={handleCompanyChange}
                                    onCompositionStart={() => { composingRef.current = true; }}
                                    onCompositionEnd={() => {
                                        composingRef.current = false;
                                        // compositionend が来た時も一応適用
                                        applyPendingSelect();
                                    }}
                                    onBlur={() => {
                                        // ★ blur が来た時に pending を適用（これが効く）
                                        composingRef.current = false;
                                        applyPendingSelect();
                                    }}
                                />
                            </div>

                            {suggestions.length > 0 && (
                            <div className="suggest-panel">
                                {isSuggestLoading && <div className="suggest-loading"></div>}

                                {suggestions.map((name) => (
                                <div
                                    key={name}
                                    className="suggest-row"
                                    onMouseDown={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();

                                        if (composingRef.current) {
                                        // ★変換中：選択を保留して、input を blur して確定させる
                                        pendingSelectRef.current = name;
                                        requestAnimationFrame(() => inputRef.current?.blur());
                                        return;
                                        }

                                        // 変換中じゃない：そのまま即選択
                                        handleSuggestionClick(name);
                                    }}
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
