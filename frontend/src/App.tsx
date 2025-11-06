import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Clients from "./pages/Clients";
import PensionFunds from "./pages/PensionFunds";
import AdditionalIncome from "./pages/AdditionalIncome";
import CapitalAssets from "./pages/CapitalAssets";  // Updated import - now from modular structure
import RetirementScenarios from "./pages/RetirementScenarios";
import SimpleFixation from "./pages/SimpleFixation";
import SimpleCurrentEmployer from "./pages/SimpleCurrentEmployer";
import SimpleGrants from "./pages/SimpleGrants";
import ReportsPage from "./pages/Reports";
import SystemSettings from "./pages/SystemSettings";
import PensionPortfolio from "./pages/PensionPortfolio";
import ClientDetailsPage from "./pages/ClientDetails";
import SystemSnapshot from "./components/SystemSnapshot";
import { getTaxBrackets } from "./components/reports/calculations/taxCalculations";
import "./styles/modern-theme.css";

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
            <Route path="/clients/:id" element={<ClientDetailsPage />} />
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
