    // AppHeader.jsx
    import { useNavigate } from "react-router-dom";
    import GridMenuModal from "./GridMenuModal";

    export default function AppHeader({ title, onLogout }) {
        const navigate = useNavigate();
        const handleLogout = () => {
            localStorage.removeItem("jobnaviUser");
            navigate("/");        // ログイン画面へ
        };
    return (
    <>
        <style>{`
        .app-header {
            height: 64px;
            min-height: 64px;
            max-height: 64px;
            padding: 0;
            padding-right: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            background-color: #ffd93d;
            color: #ffffff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.12);
        }

        .app-header-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .app-header-logo {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            object-fit: cover;
            background-color: rgba(255, 255, 255, 0.2);
        }

        .app-header-title {
            font-size: 22px;
            font-weight: 700;
            line-height: 1; 
        }

        .app-header-right {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        /* ===== ログアウトボタン本体 ===== */
        .logout-btn {
            width: 48px;
            height: 48px;
            padding: 0;
            border: none;
            background: transparent;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* アイコン全体（中身をまとめる箱） */
        .logout-icon {
            position: relative;
            width: 28px;
            height: 28px;
        }

        /* コの字（ドア） */
        .logout-door {
            position: absolute;
            left: 3px;
            top: 3px;
            width: 20px;
            height: 24px;
            border: 3px solid #ffffff;
            border-right: none;
            border-radius: 2px;
            box-sizing: border-box;
        }

        /* 矢印の棒部分 → */
        .logout-arrow {
            position: absolute;
            right: 1px;
            top: 50%;
            width: 14px;
            height: 3px;
            background-color: #ffffff;
            transform: translateY(-50%);
        }

        /* 矢印の先端（> の三角） */
        .logout-arrow::after {
            content: "";
            position: absolute;
            right: -2px;
            top: 50%;
            width: 10px;
            height: 10px;
            border-top: 3px solid #ffffff;
            border-right: 3px solid #ffffff;
            transform: translateY(-50%) rotate(45deg);
            box-sizing: border-box;
        }

        `}</style>

        <header className="app-header">
        <div className="app-header-left">
            <button
                type="button"
                aria-label="ログアウト"
                className="logout-btn"
                onClick={handleLogout}
            >
            <span className="logout-icon">
                <span className="logout-door"></span>
                <span className="logout-arrow"></span>
            </span>
            </button>
            <span className="app-header-title">{title}</span>
        </div>

        <div className="app-header-right">
            <GridMenuModal />
        </div>
        </header>
    </>
    );
    }
