// GridMenuModal.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import jobnaviImg from "../assets/jobnavi.png";
import sonsonImg from "../assets/sonson.png";
import passwordImg from "../assets/password.png";
import inteligensImg from "../assets/inteligens.png";

export default function GridMenuModal() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const handleToggle = () => setOpen((prev) => !prev);
  const handleClose = () => setOpen(false);
  const handleClickInteligens = () => {
    const stored = localStorage.getItem("jobnaviUser");
    setOpen(false);

    if (stored) {
      // ログイン中 → 検索画面へ
      navigate("/search");
    } else {
      // 未ログイン → ログイン画面へ
      navigate("/loginpage"); // ルーティングに合わせて変更
    }
  };
  return (
    <>
      <style>{`
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
          background-color: #ffffff;
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
          overflow: visible; /* はみ出し防止で追加しておくと安心 */
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
          color: #000000ff;
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
      `}</style>

      {/* ヘッダーのグリッドボタン */}
      <button type="button" className="grid-menu-btn" onClick={handleToggle}>
        <div className="grid-menu-icon">
          {Array.from({ length: 9 }).map((_, i) => (
            <span key={i} className="grid-menu-dot" />
          ))}
        </div>
      </button>

      {/* モーダル */}
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
    </>
  );
}
