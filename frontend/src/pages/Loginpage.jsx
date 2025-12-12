import { useState } from "react";
import { useNavigate } from "react-router-dom";
import jobnaviImg from "../assets/jobnavi.png";
import sonsonImg from "../assets/sonson.png";
import passwordImg from "../assets/password.png";
import inteligensImg from "../assets/inteligens.png";
import inteligensCube from "../assets/InteligensCube.png";
import reportImg from "../assets/report.png";
import { DUMMY_USERS } from "../data/usersDummy";
import '../css/Loginpage.css';

export default function Loginpage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [open, setOpen] = useState(false);
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
