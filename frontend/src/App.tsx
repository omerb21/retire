import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Clients from "./pages/Clients";
import Tools from "./pages/Tools";
import PensionFunds from "./pages/PensionFunds";
import AdditionalIncome from "./pages/AdditionalIncome";
import CapitalAssets from "./pages/CapitalAssets";
import Scenarios from "./pages/Scenarios";
import SimpleFixation from "./pages/SimpleFixation";
import SimpleCurrentEmployer from "./pages/SimpleCurrentEmployer";
import SimpleGrants from "./pages/SimpleGrants";
import SimpleReports from "./pages/SimpleReports";
import SystemSettings from "./pages/SystemSettings";
// Create inline ClientDetails component until we implement the full version
const ClientDetails = () => {
  const clientId = window.location.pathname.split('/')[2];
  return (
    <div>
      <h2>פרטי לקוח</h2>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <a href={`/clients/${clientId}/pension-funds`} style={moduleButtonStyle}>קרנות פנסיה</a>
        <a href={`/clients/${clientId}/additional-incomes`} style={moduleButtonStyle}>הכנסות נוספות</a>
        <a href={`/clients/${clientId}/capital-assets`} style={moduleButtonStyle}>נכסי הון</a>
        <a href={`/clients/${clientId}/current-employer`} style={moduleButtonStyle}>מעסיק נוכחי</a>
        <a href={`/clients/${clientId}/grants`} style={moduleButtonStyle}>מענקים</a>
        <a href={`/clients/${clientId}/scenarios`} style={moduleButtonStyle}>תרחישים</a>
        <a href={`/clients/${clientId}/fixation`} style={moduleButtonStyle}>קיבוע מס</a>
        <a href={`/clients/${clientId}/reports`} style={moduleButtonStyle}>דוחות PDF</a>
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
            <NavLink to="/system-settings">הגדרות מערכת</NavLink>
          </nav>
        </header>
        <main style={{ padding: 16 }}>
          <Routes>
            <Route path="/clients" element={<Clients />} />
            <Route path="/clients/:id" element={<ClientDetails />} />
            <Route path="/clients/:id/pension-funds" element={<PensionFunds />} />
            <Route path="/clients/:id/additional-incomes" element={<AdditionalIncome />} />
            <Route path="/clients/:id/capital-assets" element={<CapitalAssets />} />
            <Route path="/clients/:id/current-employer" element={<SimpleCurrentEmployer />} />
            <Route path="/clients/:id/grants" element={<SimpleGrants />} />
            <Route path="/clients/:id/scenarios" element={<Scenarios />} />
            <Route path="/clients/:id/fixation" element={<SimpleFixation />} />
            <Route path="/clients/:id/reports" element={<SimpleReports />} />
            <Route path="/tools" element={<Tools />} />
            <Route path="/system-settings" element={<SystemSettings />} />
            <Route path="/" element={<Clients />} />
            <Route path="*" element={<Clients />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
