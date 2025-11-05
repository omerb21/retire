import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Clients from "./pages/Clients";
import PensionFunds from "./pages/PensionFunds";
import AdditionalIncome from "./pages/AdditionalIncome";
import CapitalAssets from "./pages/CapitalAssets";
import RetirementScenarios from "./pages/RetirementScenarios";
import SimpleFixation from "./pages/SimpleFixation";
import SimpleCurrentEmployer from "./pages/SimpleCurrentEmployer";
import SimpleGrants from "./pages/SimpleGrants";
import ReportsPage from "./pages/ReportsPage";
import SystemSettings from "./pages/SystemSettings";
import PensionPortfolio from "./pages/PensionPortfolio";
import SystemSnapshot from "./components/SystemSnapshot";
import { getTaxBrackets } from "./components/reports/calculations/taxCalculations";
import "./styles/modern-theme.css";
// Create inline ClientDetails component until we implement the full version
const ClientDetails = () => {
  const clientId = window.location.pathname.split('/')[2];
  const [client, setClient] = React.useState<any>(null);
  
  React.useEffect(() => {
    // טעינת נתוני הלקוח
    fetch(`/api/v1/clients/${clientId}`)
      .then(res => res.json())
      .then(data => setClient(data))
      .catch(err => console.error('Error loading client:', err));
  }, [clientId]);
  
  return (
    <div>
      <h2 style={{ marginBottom: '30px' }}>
        תהליך פרישה - {client ? `${client.first_name} ${client.last_name}` : '...'} 
        {client && ` (ת"ז: ${client.id_number})`}
      </h2>
      
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <a href={`/clients/${clientId}/pension-portfolio`} style={moduleButtonStyle}>תיק פנסיוני</a>
        <a href={`/clients/${clientId}/grants`} style={moduleButtonStyle}>מענקים פטורים שהתקבלו</a>
        <a href={`/clients/${clientId}/current-employer`} style={moduleButtonStyle}>מעסיק נוכחי</a>
        <a href={`/clients/${clientId}/pension-funds`} style={moduleButtonStyle}>קצבאות והיוונים</a>
        <a href={`/clients/${clientId}/additional-incomes`} style={moduleButtonStyle}>הכנסות נוספות</a>
        <a href={`/clients/${clientId}/capital-assets`} style={moduleButtonStyle}>נכסי הון</a>         
        <a href={`/clients/${clientId}/fixation`} style={moduleButtonStyle}>קיבוע זכויות</a>
        <a href={`/clients/${clientId}/reports`} style={moduleButtonStyle}>📊 תוצאות</a>
        <a href={`/clients/${clientId}/retirement-scenarios`} style={moduleButtonStyle}>🎯 תרחישי פרישה</a>
      </div>
      
      <a href="/clients" style={{ display: 'inline-block', marginBottom: '20px' }}>חזרה לרשימת לקוחות</a>
      
      {/* System Snapshot - שמירה ושחזור מצב */}
      <div style={{ 
        marginTop: '550px',
        marginBottom: '20px', 
        padding: '20px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '8px',
        border: '2px solid #dee2e6'
      }}>
        <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#495057' }}>
          🔄 שמירה ושחזור מצב מערכת
        </h3>
        <SystemSnapshot 
          clientId={parseInt(clientId)} 
          onSnapshotRestored={() => window.location.reload()}
        />
      </div>
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
  // טעינת מדרגות מס מ-API בעת טעינת האפליקציה
  useEffect(() => {
    // כרגע getTaxBrackets היא סינכרונית, נטען את המדרגות מיד
    const brackets = getTaxBrackets();
    console.log('✅ מדרגות מס אותחלו בהצלחה:', brackets.length, 'מדרגות');
  }, []);

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
            <Route path="/clients/:id/retirement-scenarios" element={<RetirementScenarios />} />
            <Route path="/clients/:id/fixation" element={<SimpleFixation />} />
            <Route path="/clients/:id/reports" element={<ReportsPage />} />
            <Route path="/system-settings" element={<SystemSettings />} />
            <Route path="/" element={<Clients />} />
            <Route path="*" element={<Clients />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
