import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { I18nextProvider } from 'react-i18next';
import i18n from './lib/i18n';
import Layout from './components/Layout';
import ClientNew from './routes/ClientNew';
import EmployerCurrent from './routes/EmployerCurrent';
import EmployersPast from './routes/EmployersPast';
import Pensions from './routes/Pensions';
import IncomeAssets from './routes/IncomeAssets';
import TaxAdmin from './routes/TaxAdmin';
import Scenarios from './routes/Scenarios';
import Results from './routes/Results';

// Create RTL theme for Hebrew
const theme = createTheme({
  direction: 'rtl',
  typography: {
    fontFamily: '"Segoe UI", "Roboto", "Arial", sans-serif',
  },
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <I18nextProvider i18n={i18n}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Router>
          <Layout>
            <Routes>
              <Route path="/" element={<ClientNew />} />
              <Route path="/client" element={<ClientNew />} />
              <Route path="/employer-current" element={<EmployerCurrent />} />
              <Route path="/employers-past" element={<EmployersPast />} />
              <Route path="/pensions" element={<Pensions />} />
              <Route path="/income-assets" element={<IncomeAssets />} />
              <Route path="/tax-admin" element={<TaxAdmin />} />
              <Route path="/scenarios" element={<Scenarios />} />
              <Route path="/results" element={<Results />} />
            </Routes>
          </Layout>
        </Router>
      </ThemeProvider>
    </I18nextProvider>
  );
}

export default App;
