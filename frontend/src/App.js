import { Routes, Route } from "react-router-dom";

import Loginpage from "./pages/Loginpage.jsx";
import Search from "./pages/Search.jsx";
import Result from "./pages/Result.jsx";
import StudentPage from "./pages/student";

export default function App() {
  return (
    <Routes>
      {/* ログイン画面 */}
      <Route path="/" element={<Loginpage />} />

      {/* ログイン後のみ使う画面 */}
      <Route path="/search" element={<Search />} />
      <Route path="/student" element={<StudentPage />} />
      <Route path="/result" element={<Result />} />

      {/* 想定外ルート */}
      <Route path="*" element={<Loginpage />} />
    </Routes>
  );
}
