import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Clients from "./pages/Clients";
import Tools from "./pages/Tools";

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ fontFamily: "system-ui, Arial", direction: "rtl" }}>
        <header style={{ padding: 16, borderBottom: "1px solid #ddd" }}>
          <nav style={{ display: "flex", gap: 16 }}>
            <NavLink to="/clients">לקוחות</NavLink>
            <NavLink to="/tools">כלי בדיקה</NavLink>
          </nav>
        </header>
        <main style={{ padding: 16 }}>
          <Routes>
            <Route path="/clients" element={<Clients />} />
            <Route path="/tools" element={<Tools />} />
            <Route path="*" element={<Clients />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
