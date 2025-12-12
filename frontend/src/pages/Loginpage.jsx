// Loginpage.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import jobnaviImg from "../assets/jobnavi.png";
import sonsonImg from "../assets/sonson.png";
import passwordImg from "../assets/password.png";
import inteligensImg from "../assets/inteligens.png";
import inteligensCube from "../assets/InteligensCube.png";
import reportImg from "../assets/report.png";
import { DUMMY_USERS } from "../data/usersDummy";

export default function Loginpage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [open, setOpen] = useState(false);      // ← グリッドモーダル用
    const navigate = useNavigate();

    const [error, setError] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    const isFormValid = email.trim().length > 0 && password.trim().length > 0;

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!isFormValid || isSubmitting) return;

        setError("");
        setIsSubmitting(true);

        try {
            const trimmedEmail = email.trim();
            const trimmedPassword = password.trim();

            // メールアドレス一致ユーザーを検索
            const user = DUMMY_USERS.find((u) => u.email === trimmedEmail);

            // ユーザーなし or パスワード不一致
            if (!user || user.password !== trimmedPassword) {
                setError("メールアドレスまたはパスワードが違います。");
                return;
            }

            // ログイン情報を保存（パスワードは保存しない）
            localStorage.setItem(
                "jobnaviUser",
                JSON.stringify({
                    email: user.email,
                    role: user.role, // "student"/"teacher"/"admin"
                    name: user.name,
                })
            );

            // 検索画面へ遷移
            navigate("/search");
        } finally {
            setIsSubmitting(false);
        }
    };
    const handleToggle = () => setOpen((prev) => !prev);
    const handleClose = () => setOpen(false);
    // ★ Inteligens クリック時：ログイン状態で遷移先分岐
    const handleClickInteligens = () => {
        const stored = localStorage.getItem("jobnaviUser");
        setOpen(false);
        console.log("inteligensImg =", inteligensImg);
        if (stored) {
            // ログイン中 → 検索画面へ
            navigate("/search");
        } else {
            // 未ログイン → ログイン画面へ（このコンポーネント自身）
            navigate("/loginpage"); // ルーティングによっては "/login" などに変更
        }
    };

    const handleClickStudent = () => {
        const stored = localStorage.getItem("jobnaviUser");
        setOpen(false);
        console.log("reportImg =", reportImg);
        if (stored) {
            // ログイン中 → 検索画面へ
            navigate("/student");
        } else {
            // 未ログイン → ログイン画面へ（このコンポーネント自身）
            navigate("/loginpage"); // ルーティングによっては "/login" などに変更
        }
    };
    return (
        <div className="login-root">
            <style>{`
        .login-root {
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background-color: #ffffff;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            position: relative;
        }

        /* 右上配置用ラッパ */
        .login-grid-wrapper {
            position: fixed;
            top: 16px;
            right: 16px;
            z-index: 1100;
        }

        /* ===== ここからグリッドモーダル用（指定どおり） ===== */
        .grid-menu-btn {
            background: none;
            border: none;
            cursor: pointer;
            padding: 0;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .grid-menu-icon {
            width: 26px;
            height: 26px;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            grid-template-rows: repeat(3, 1fr);
            gap: 4px;
        }

        .grid-menu-dot {
            width: 5px;
            height: 5px;
            background-color: #e9e7e7ff;
            border-radius: 50%;
        }

        .grid-menu-overlay {
            position: fixed;
            inset: 0;
            background-color: rgba(0, 0, 0, 0.45);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .grid-menu-dialog {
            background-color: #ffffff;
            padding: 30px 50px;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            min-width: 320px;
            max-width: 420px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            overflow: visible;
        }

        .grid-menu-card {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 10px 16px;
            border-radius: 999px;
            background-color: #f4f4f4;
            cursor: pointer;
        }

        .grid-menu-img {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
        }

        .grid-menu-text {
            font-size: 16px;
            font-weight: 500;
        }

        .grid-menu-close-btn {
            align-self: flex-start;
            margin-top: 14px;
            padding: 6px 18px;
            border-radius: 6px;
            border: 1px solid #bdbdbd;
            background-color: #ffffff;
            cursor: pointer;
        }

        .grid-menu-version {
            margin-top: 8px;
            font-size: 12px;
            color: #666666;
            align-self: center;
        }
        /* ===== グリッドモーダルここまで ===== */

        .login-card {
            width: 360px;
            background-color: #ffffff;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
            overflow: hidden;
        }

        .login-header {
            background-color: #ffd93d;
            color: #ffffff;
            text-align: center;
            padding: 12px 0;
            font-size: 20px;
            font-weight: 600;
        }

        .login-body {
            padding: 24px 32px 28px;
        }

        .login-field {
            margin-bottom: 16px;
        }

        .login-label {
            display: block;
            font-size: 13px;
            margin-bottom: 6px;
            color: #555555;
        }

        .login-input {
            width: 100%;
            height: 40px;
            padding: 0 10px;
            border-radius: 2px;
            border: 1px solid #d0d0d0;
            font-size: 14px;
            box-sizing: border-box;
        }

        .login-input:focus {
            outline: none;
            border-color: #ffd93d;
            box-shadow: 0 0 0 1px rgba(11, 99, 206, 0.2);
        }

        .login-button {
            width: 100%;
            height: 40px;
            border: none;
            border-radius: 2px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            background-color: #e0e0e0;
            color: #9e9e9e;
        }

        .login-button--active {
            background-color: #ffd93d;
            color: #ffffff;
        }

        .login-button:disabled {
            cursor: default;
        }

        .login-footer {
            margin-top: 80px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }

        .login-cube {
            width: 90px;
            height: 80px;
            animation: cube-rotate 11s linear infinite;
        }

        .login-version {
            font-size: 13px;
            color: #555555;
        }

        @keyframes cube-rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        @media (max-width: 480px) {
            .login-card {
            width: calc(100% - 32px);
            }
            .login-body {
            padding: 20px 16px 24px;
            }
        }
        `}</style>

            {/* 右上のグリッドメニュー */}
            <div className="login-grid-wrapper">
                <button
                    type="button"
                    className="grid-menu-btn"
                    onClick={handleToggle}
                >
                    <div className="grid-menu-icon">
                        {Array.from({ length: 9 }).map((_, i) => (
                            <span key={i} className="grid-menu-dot" />
                        ))}
                    </div>
                </button>
            </div>

            {/* モーダル（内容は指定コードと同じ） */}
            {open && (
                <div className="grid-menu-overlay" onClick={handleClose}>
                    <div
                        className="grid-menu-dialog"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* ① JobNavi */}
                        <div className="grid-menu-card">
                            <img className="grid-menu-img" src={jobnaviImg} alt="JobNavi" />
                            <p className="grid-menu-text">JobNavi</p>
                        </div>

                        {/* ② 受験報告閲覧 */}
                        <div className="grid-menu-card">
                            <img className="grid-menu-img" src={sonsonImg} alt="受験報告閲覧" />
                            <p className="grid-menu-text">受験報告閲覧</p>
                        </div>

                        {/* ③ パスワード変更 */}
                        <div className="grid-menu-card">
                            <img className="grid-menu-img" src={passwordImg} alt="パスワード変更" />
                            <p className="grid-menu-text">パスワード変更</p>
                        </div>

                        {/* ④ Inteligens（新規） */}
                        <div
                            className="grid-menu-card"
                            onClick={handleClickInteligens}
                        >
                            <img className="grid-menu-img" src={inteligensImg} alt="Inteligens" />
                            <p className="grid-menu-text">Inteligens</p>
                        </div>

                        {/* ⑤ 受験分析レポート（新規） */}
                        <div
                            className="grid-menu-card"
                            onClick={handleClickStudent}
                        >
                            <img className="grid-menu-img" src={reportImg} alt="受験分析レポート" />
                            <p className="grid-menu-text">受験分析レポート</p>
                        </div>

                        <button
                            type="button"
                            className="grid-menu-close-btn"
                            onClick={handleClose}
                        >
                            Close
                        </button>

                        <span className="grid-menu-version">v1.1.0</span>
                    </div>
                </div>
            )}

            {/* ログインカード */}
            <div className="login-card">
                <div className="login-header">Inteligens</div>

                <form className="login-body" onSubmit={handleSubmit}>
                    <div className="login-field">
                        <input
                            className="login-input"
                            type="email"
                            placeholder="メールアドレス"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>

                    <div className="login-field">
                        <input
                            className="login-input"
                            type="password"
                            placeholder="パスワード"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                        />
                    </div>
                    {error && <p className="login-error">{error}</p>}
                    <button
                        type="submit"
                        className={`login-button ${isFormValid ? "login-button--active" : ""}`}
                        disabled={!isFormValid || isSubmitting}
                    >
                        ログイン
                    </button>
                </form>
            </div>

            {/* 下部のキューブ＆バージョン表記 */}
            <div className="login-footer">
                <img
                    className="login-cube"
                    src={inteligensCube}
                    alt="JobNavi cube logo"
                />
                <div className="login-version">JobNavi v2.5.3</div>
            </div>
        </div>

    );
}
