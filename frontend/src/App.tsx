import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Clients from "./pages/Clients";
import Tools from "./pages/Tools";
import PensionFunds from "./pages/PensionFunds";
import AdditionalIncome from "./pages/AdditionalIncome";
import CapitalAssets from "./pages/CapitalAssets";
import Scenarios from "./pages/Scenarios";
import Fixation from "./pages/Fixation";
// Create inline ClientDetails component until we implement the full version
const ClientDetails = () => {
  const clientId = window.location.pathname.split('/')[2];
  return (
    <div>
      <h2>פרטי לקוח</h2>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <a href={`/clients/${clientId}/pension-funds`} style={moduleButtonStyle}>קרנות פנסיה</a>
        <a href={`/clients/${clientId}/additional-income`} style={moduleButtonStyle}>הכנסות נוספות</a>
        <a href={`/clients/${clientId}/capital-assets`} style={moduleButtonStyle}>נכסי הון</a>
        <a href={`/clients/${clientId}/scenarios`} style={moduleButtonStyle}>תרחישים</a>
        <a href={`/clients/${clientId}/fixation`} style={moduleButtonStyle}>קיבוע מס</a>
      </div>
      <a href="/clients">חזרה לרשימת לקוחות</a>
    </div>
  );
};

// Style for module buttons
const moduleButtonStyle = {
  padding: '10px 15px',
  backgroundColor: '#f0f0f0',
  borderRadius: '4px',
  textDecoration: 'none',
  color: '#333',
  fontWeight: 'bold' as 'bold'
};
// Import module components (placeholders until implemented)
// All modules now imported from separate files

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
            <Route path="/clients/:id" element={<ClientDetails />} />
            <Route path="/clients/:id/pension-funds" element={<PensionFunds />} />
            <Route path="/clients/:id/additional-income" element={<AdditionalIncome />} />
            <Route path="/clients/:id/capital-assets" element={<CapitalAssets />} />
            <Route path="/clients/:id/scenarios" element={<Scenarios />} />
            <Route path="/clients/:id/fixation" element={<Fixation />} />
            <Route path="/tools" element={<Tools />} />
            <Route path="/" element={<Clients />} />
            <Route path="*" element={<Clients />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
