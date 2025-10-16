import React from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Clients from "./pages/Clients";
import PensionFunds from "./pages/PensionFunds";
import AdditionalIncome from "./pages/AdditionalIncome";
import CapitalAssets from "./pages/CapitalAssets";
import Scenarios from "./pages/Scenarios";
import SimpleFixation from "./pages/SimpleFixation";
import SimpleCurrentEmployer from "./pages/SimpleCurrentEmployer";
import SimpleGrants from "./pages/SimpleGrants";
import SimpleReports from "./pages/SimpleReports";
import SystemSettings from "./pages/SystemSettings";
import PensionPortfolio from "./pages/PensionPortfolio";
import "./styles/modern-theme.css";
// Create inline ClientDetails component until we implement the full version
const ClientDetails = () => {
  const clientId = window.location.pathname.split('/')[2];
  return (
    <div>
      <h2>פרטי לקוח</h2>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <a href={`/clients/${clientId}/pension-portfolio`} style={moduleButtonStyle}>תיק פנסיוני</a>
        <a href={`/clients/${clientId}/pension-funds`} style={moduleButtonStyle}>קצבאות והיוונים</a>
        <a href={`/clients/${clientId}/additional-incomes`} style={moduleButtonStyle}>הכנסות נוספות</a>
        <a href={`/clients/${clientId}/capital-assets`} style={moduleButtonStyle}>נכסי הון</a>
        <a href={`/clients/${clientId}/current-employer`} style={moduleButtonStyle}>מעסיק נוכחי</a>
        <a href={`/clients/${clientId}/grants`} style={moduleButtonStyle}>מענקים</a>
        <a href={`/clients/${clientId}/fixation`} style={moduleButtonStyle}>קיבוע זכויות</a>
        <a href={`/clients/${clientId}/scenarios`} style={moduleButtonStyle}>תרחישים</a>
        <a href={`/clients/${clientId}/reports`} style={moduleButtonStyle}>📊 תוצאות</a>
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
      <div>
        <header className="modern-header">
          <div className="header-container">
            <div className="logo-section">
              <img 
                src="/LOGO.png" 
                alt="Logo" 
                className="logo-image"
              />
              <h1 className="system-title">מערכת תכנון פרישה</h1>
            </div>
            <nav className="modern-nav">
              <NavLink 
                to="/clients" 
                className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}
              >
                לקוחות
              </NavLink>
              <NavLink 
                to="/system-settings"
                className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}
              >
                הגדרות מערכת
              </NavLink>
            </nav>
          </div>
        </header>
        <main className="main-content">
          <Routes>
            <Route path="/clients" element={<Clients />} />
            <Route path="/clients/:id" element={<ClientDetails />} />
            <Route path="/clients/:id/pension-portfolio" element={<PensionPortfolio />} />
            <Route path="/clients/:id/pension-funds" element={<PensionFunds />} />
            <Route path="/clients/:id/additional-incomes" element={<AdditionalIncome />} />
            <Route path="/clients/:id/capital-assets" element={<CapitalAssets />} />
            <Route path="/clients/:id/current-employer" element={<SimpleCurrentEmployer />} />
            <Route path="/clients/:id/grants" element={<SimpleGrants />} />
            <Route path="/clients/:id/scenarios" element={<Scenarios />} />
            <Route path="/clients/:id/fixation" element={<SimpleFixation />} />
            <Route path="/clients/:id/reports" element={<SimpleReports />} />
            <Route path="/system-settings" element={<SystemSettings />} />
            <Route path="/" element={<Clients />} />
            <Route path="*" element={<Clients />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
