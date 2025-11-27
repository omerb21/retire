import React, { useEffect, useState, useCallback } from "react";
import { HashRouter, Routes, Route, NavLink } from "react-router-dom";
import { getTaxBrackets } from "./components/reports/calculations/taxCalculations";
import "./styles/modern-theme.css";
import SystemAccessGate from "./components/SystemAccess/SystemAccessGate";

// Lazy-loaded page components for better bundle splitting
const Clients = React.lazy(() => import("./pages/Clients/ClientsPage"));
const PensionFunds = React.lazy(() => import("./pages/PensionFunds"));
const AdditionalIncome = React.lazy(
  () => import("./pages/AdditionalIncome/components/AdditionalIncomePage")
);
const CapitalAssets = React.lazy(() => import("./pages/CapitalAssets"));
const RetirementScenarios = React.lazy(
  () => import("./pages/RetirementScenarios/components/RetirementScenariosPage")
);
const SimpleFixation = React.lazy(() => import("./pages/SimpleFixation/SimpleFixationPage"));
const SimpleCurrentEmployer = React.lazy(() => import("./pages/SimpleCurrentEmployer"));
const SimpleGrants = React.lazy(() => import("./pages/SimpleGrants"));
const ReportsPage = React.lazy(() => import("./pages/Reports"));
const SystemSettings = React.lazy(() => import("./pages/SystemSettings"));
const PensionPortfolio = React.lazy(() => import("./pages/PensionPortfolio"));
const ClientDetailsPage = React.lazy(() => import("./pages/ClientDetails"));

// Import module components (placeholders until implemented)
// All modules now imported from separate files

const SYSTEM_ACCESS_STORAGE_KEY = "systemAccessPassword";

export default function App() {
  // טעינת מדרגות מס מ-API בעת טעינת האפליקציה
  const [hasAccess, setHasAccess] = useState(false);

  const handleAccessGranted = useCallback(() => {
    setHasAccess(true);
  }, []);

  useEffect(() => {
    // כרגע getTaxBrackets היא סינכרונית, נטען את המדרגות מיד
    const brackets = getTaxBrackets();
    console.log('✅ מדרגות מס אותחלו בהצלחה:', brackets.length, 'מדרגות');
  }, []);

  useEffect(() => {
    const existing = window.localStorage.getItem(SYSTEM_ACCESS_STORAGE_KEY);
    if (existing) {
      setHasAccess(true);
    }
  }, []);

  if (!hasAccess) {
    return <SystemAccessGate onAccessGranted={handleAccessGranted} />;
  }

  return (
    <HashRouter>
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
          <React.Suspense
            fallback={
              <div className="loading-fallback">
                <div className="spinner" />
                <span className="loading-text">טוען...</span>
              </div>
            }
          >
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
          </React.Suspense>
        </main>
      </div>
    </HashRouter>
  );
}
