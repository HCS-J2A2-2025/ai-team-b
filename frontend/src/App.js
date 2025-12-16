import Loginpage from "./pages/Loginpage.jsx";
import Search from "./pages/Search.jsx";
import Result from "./pages/Result.jsx";
import { Routes, Route } from "react-router-dom";
import StudentPage from "./pages/student";

export default function App() {
  //const [name, setName] = useState("");
  //const [result, setResult] = useState("");

  /*const handleSearch = async () => {
    if (!name) return;

    try {
      const res = await fetch(`http://localhost:8000/company/${name}`);
      const data = await res.json();

      if (data.error) {
        setResult("企業が見つかりません");
      } else {
        setResult(data.report);
      }
    } catch (error) {
      setResult("API 接続エラー");
    }
  };*/

  return (

  // <div style={{ padding: "40px" }}>
  //   <h1>企業レポートAI</h1>

  //   <input
  //     type="text"
  //     placeholder="企業名を入力"
  //     value={name}
  //     onChange={(e) => setName(e.target.value)}
  //     style={{ padding: "10px", width: "300px" }}
  //   />
  //   <button onClick={handleSearch} style={{ marginLeft: "10px", padding: "10px" }}>
  //     検索
  //   </button>

  //   <pre style={{ marginTop: "20px", background: "#eee", padding: "20px", whiteSpace: "pre-wrap" }}>
  //     {result}
  //   </pre>
  // </div>

  <Routes>
      {/* 最初の画面 = ログイン */}
      <Route path="/" element={<Loginpage />} />
    {/* ログイン成功後の画面 */}
      <Route path="/search" element={<Search />} />
      <Route path="/student" element={<StudentPage />} />
      {/* 検索結果（左右に分割される画面） */}
      <Route path="/result" element={<Result />} />
  </Routes>
  );

}
