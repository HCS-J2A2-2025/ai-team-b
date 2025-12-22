import { Routes, Route, useLocation } from "react-router-dom";
import { useEffect } from "react";

import Loginpage from "./pages/Loginpage.jsx";
import Search from "./pages/Search.jsx";
import Result from "./pages/Result.jsx";
import StudentPage from "./pages/student";
import TetrisPage from "./pages/TetrisPage.jsx";
import YachtGame from "./pages/YachtGame.jsx";

const KEY = "mem_path";

export default function App() {
  const location = useLocation();

  // ✅ 今いる画面を保存（F5しても戻れる）
  useEffect(() => {
    sessionStorage.setItem(KEY, location.pathname + location.search);
  }, [location.pathname, location.search]);

  return (
    <Routes>
      {/* ログイン画面 */}
      <Route path="/" element={<Loginpage />} />

      {/* ログイン後画面（URLは変わらないが内部的に遷移） */}
      <Route path="/search" element={<Search />} />
      <Route path="/student" element={<StudentPage />} />
      <Route path="/result" element={<Result />} />

      {/* ゲーム系 */}
      <Route path="/tetris" element={<TetrisPage />} />
      <Route path="/game/yacht" element={<YachtGame />} />

      {/* 想定外ルート → ログイン */}
      <Route path="*" element={<Loginpage />} />
    </Routes>
  );
}
