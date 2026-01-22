// Search.jsx
import { useState, useRef, useEffect } from "react";
import AppHeader from "../components/AppHeader";
import { useNavigate } from "react-router-dom";
import "../css/Search.css";

export default function Search() {
const [company, setCompany] = useState("");
const [suggestions, setSuggestions] = useState([]);
const [isSuggestLoading, setIsSuggestLoading] = useState(false);

const [selectedFile, setSelectedFile] = useState(null); // 選択中CSV
const [isDragOver, setIsDragOver] = useState(false); // ドラッグ中か
const [role, setRole] = useState(null);

const [isSubmitting, setIsSubmitting] = useState(false);
const [showSubmitting, setShowSubmitting] = useState(false);
const [apiError, setApiError] = useState(null);

const fileInputRef = useRef(null);
const navigate = useNavigate();

const suggestAbortRef = useRef(null);
const suppressSuggestRef = useRef(false); // サジェスト確定クリック直後の“復活”を抑止
const suggestSeqRef = useRef(0); // 古いレスポンスを捨てる番号
const suggestTimerRef = useRef(null);
const lastSuggestKeyRef = useRef("");
const suggestCacheRef = useRef(new Map());

const composingRef = useRef(false);
const pendingSelectRef = useRef(null);
const inputRef = useRef(null);

//検索バー+サジェスト領域を参照（外側クリックで閉じるため）
const searchWrapperRef = useRef(null);

// Search.jsx
const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:8000";

// 表示重複を潰すための「同一視キー」
// ※法人格の位置（前株/後株）はここでは変えない。あくまで重複判定だけ。
const normalizeCompanyKey = (s) => {
  if (!s) return "";
  return String(s)
    .trim()
    .replace(/\s+/g, "")
    .replace(/[()（）【】［］]/g, "")
    .replace(/㈱|株式会社|（株）|\(株\)/g, "")
    .toLowerCase();
};

const uniqByCompanyKey = (arr) => {
  const out = [];
  const seen = new Set();
  for (const name of arr || []) {
    const k = normalizeCompanyKey(name);
    if (!k || seen.has(k)) continue;
    seen.add(k);
    out.push(name); // 表示は「最初に来た表記」を採用（勝手に前株/後株に変えない）
  }
  return out;
};



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
    if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
};
}, [navigate]);

// 外側クリックでサジェストを閉じる
useEffect(() => {
const onDocMouseDown = (e) => {
    const root = searchWrapperRef.current;
    if (!root) return;

    // search-wrapper の外をクリックしたら閉じる
    if (!root.contains(e.target)) {
    setSuggestions([]);
    setIsSuggestLoading(false);
    // 進行中の通信も止める（無駄な更新防止）
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
    suggestSeqRef.current++;
    }
};

document.addEventListener("mousedown", onDocMouseDown);
return () => document.removeEventListener("mousedown", onDocMouseDown);
}, []);

// 検索ボタン押したときに /result へ遷移 + 会社名を渡す
const handleSubmit = async (e) => {
  e.preventDefault();
  const raw = company.trim();
  if (!raw || isSubmitting) return;

  setIsSubmitting(true);
  setApiError(null);
    try {
    const cached =
        lastSuggestKeyRef.current === raw ? suggestions : suggestCacheRef.current.get(raw);
    const candidates = Array.isArray(cached) ? cached : [];

    if (candidates.length === 0) {
        // ✅ suggestで「CSV上の正式名」を取って、それで遷移する
        const sres = await fetch(`${API_BASE}/api/company/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: raw }),
        });

        const sjson = await sres.json().catch(() => ({}));
        if (!sres.ok) {
        setApiError(`入力チェックに失敗しました（HTTP ${sres.status}）`);
        return;
        }

        const fetchedRaw = Array.isArray(sjson?.candidates) ? sjson.candidates : [];
        const fetched = uniqByCompanyKey(fetchedRaw);

        if (fetched.length === 0) {
        setApiError("企業名が見つかりませんでした（候補なし）");
        return;
        }

        suggestCacheRef.current.set(raw, fetched);
        const canonicalName = String(fetched[0]).trim();

        navigate("/result", { state: { companyName: canonicalName } });
        return;
    }

    const canonicalName = String(candidates[0]).trim();
    navigate("/result", { state: { companyName: canonicalName } });
    } catch (err) {
    setApiError("API 接続エラー：サーバーに接続できませんでした");
    }

};


const handleLogout = () => {
console.log("ログアウトしました");
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
if (fileInputRef.current) fileInputRef.current.click();
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
};

const removeSelectedFile = () => {
setSelectedFile(null);
if (fileInputRef.current) {
    fileInputRef.current.value = "";
}
};

const handleCsvUpload = async (file) => {
  if (!file) return;

  const formData = new FormData();   // ← これが必須
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/upload_csv`, {  // ← API_BASE を付ける
      method: "POST",
      body: formData,
    });

    const data = await res.json().catch(() => ({}));

    if (data.status === "ok") {
      alert("CSV アップロード成功: " + data.filename);
    } else {
      alert("CSV アップロードエラー: " + (data.message ?? "unknown"));
    }
  } catch (e) {
    alert("サーバーに接続できません（API エラー）");
  }
};


// サジェスト取得処理を関数化（onChange と onClick から共通利用）
const requestSuggest = async (keyword) => {
// 確定クリック直後は走らせない（復活防止）
if (suppressSuggestRef.current) return;

const key = (keyword ?? "").trim();

// 空なら候補消す＆通信止める
if (!key) {
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
    setSuggestions([]);
    setIsSuggestLoading(false);
    return;
}

const cached = suggestCacheRef.current.get(key);
if (Array.isArray(cached)) {
  setSuggestions(uniqByCompanyKey(cached)); // ★復活対策
  setIsSuggestLoading(false);
  lastSuggestKeyRef.current = key;
  return;
}

if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
if (suggestAbortRef.current) suggestAbortRef.current.abort();
setIsSuggestLoading(true);

suggestTimerRef.current = setTimeout(async () => {
    // この入力に対するリクエスト番号
    const seq = ++suggestSeqRef.current;

    // 前回を中断
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    const controller = new AbortController();
    suggestAbortRef.current = controller;

    try {
    const res = await fetch(`${API_BASE}/api/company/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: key }),
        signal: controller.signal,
    });

    const data = await res.json().catch(() => ({}));

    // 古い返りは捨てる
    if (seq !== suggestSeqRef.current) return;
    if (suppressSuggestRef.current) return;

    if (!res.ok) {
        setSuggestions([]);
        return;
    }

    const rawList = Array.isArray(data?.candidates) ? data.candidates : [];
    const list = uniqByCompanyKey(rawList);

    suggestCacheRef.current.set(key, list);   // ★必ず uniq 済みをキャッシュ
    lastSuggestKeyRef.current = key;
    setSuggestions(list);
    } catch (err) {
    if (err?.name !== "AbortError") console.error("候補取得エラー:", err);
    if (seq !== suggestSeqRef.current) return;
    setSuggestions([]);
    } finally {
    if (seq === suggestSeqRef.current) setIsSuggestLoading(false);
    }
}, 250);
};

// 「㈱」を入力欄のカーソル位置に挿入（重複は避ける）
const handleInsertKabu = () => {
  const kabu = "㈱";
  const el = inputRef.current;
  const v = company ?? "";

  // すでに入っている場合は追加しない（誤爆防止）
  if (v.includes(kabu)) {
    requestAnimationFrame(() => el?.focus());
    return;
  }

  const start = typeof el?.selectionStart === "number" ? el.selectionStart : v.length;
  const end = typeof el?.selectionEnd === "number" ? el.selectionEnd : v.length;

  const next = v.slice(0, start) + kabu + v.slice(end);
  setCompany(next);
  setApiError(null);
  requestSuggest(next);

  requestAnimationFrame(() => {
    el?.focus();
    try {
      el?.setSelectionRange(start + kabu.length, start + kabu.length);
    } catch {}
  });
};

const handleCompanyChange = async (e) => {
const value = e.target.value;
setCompany(value);
setApiError(null);

// 入力が変わった兆し → サジェスト更新
requestSuggest(value);
};

// クリックなど「入力する兆し」でサジェストを再表示したい
const handleInputClick = () => {
// クリックした兆し → 現在値でサジェスト再取得（空なら何もしない）
requestSuggest(company);
};

const handleSuggestionClick = (name) => {
suppressSuggestRef.current = true;

// 進行中のサジェスト通信を止める
if (suggestAbortRef.current) suggestAbortRef.current.abort();
suggestSeqRef.current++; // 遅れて返ったやつは捨てる

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
<div className="app-root">
    <AppHeader title="JobNavi Inteligens" onLogout={handleLogout} />

    <main className="app-main">
    {showSubmitting && (
        <div className="loading-backdrop">
        <div className="loading-box">
            <div className="loading-text">AI要約レポートを生成しています…</div>
            <div className="loading-spinner" />
        </div>
        </div>
    )}

    <section>
        <h1 className="main-title">JobNavi Inteligens</h1>

        <form className="search-area" onSubmit={handleSubmit}>
        {/* search-wrapper を ref で囲う（外側クリック検知の基準） */}
        <div className="search-wrapper" ref={searchWrapperRef}>
            <div
            className={`search-input-wrapper ${
                suggestions.length > 0 ? "has-suggest" : ""
            }`}
            >
            <span className="search-icon">🔍</span>
            <button
                type="button"
                className="kabu-inline-btn"
                title="㈱を入力"
                aria-label="㈱を入力"
                onMouseDown={(e) => e.preventDefault()}
                onClick={handleInsertKabu}
            >
                ㈱
            </button>
            <input
                ref={inputRef}
                type="text"
                className="search-input"
                placeholder="会社名を記入　 例）ダイアモンドヘッド"
                value={company}
                onChange={handleCompanyChange}
                // onFocus は使わない（student と同じ方針）
                onClick={handleInputClick}
                onCompositionStart={() => {
                composingRef.current = true;
                }}
                onCompositionEnd={() => {
                composingRef.current = false;
                applyPendingSelect();
                }}
                onBlur={() => {
                // 変換中にサジェスト選択したケースを確定させる
                composingRef.current = false;
                applyPendingSelect();
                }}
            />
            </div>

            {suggestions.length > 0 && (
            <div className="suggest-panel">
                {isSuggestLoading && (
                <div className="suggest-loading"></div>
                )}

                {suggestions.map((name) => (
                <div
                    key={name}
                    className="suggest-row"
                    onMouseDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();

                    if (composingRef.current) {
                        // 変換中：選択を保留して input を blur
                        pendingSelectRef.current = name;
                        requestAnimationFrame(() => inputRef.current?.blur());
                        return;
                    }

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

    {role === "admin" && (
        <section className="upload-section">
        <div className="upload-title">CSV一括登録（管理者用）</div>

        <div
            className={`upload-box ${isDragOver ? "drag-over" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleBrowseClick}
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

            <input
            type="file"
            accept=".csv"
            ref={fileInputRef}
            style={{ display: "none" }}
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
);
}
