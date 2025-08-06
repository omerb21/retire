import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AppBar,
  Toolbar,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  IconButton,
  Box,
  Stepper,
  Step,
  StepLabel,
  Chip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Person as PersonIcon,
  Work as WorkIcon,
  History as HistoryIcon,
  AccountBalance as PensionIcon,
  AttachMoney as MoneyIcon,
  Settings as SettingsIcon,
  Analytics as ScenariosIcon,
  Assessment as ResultsIcon,
} from '@mui/icons-material';
import { useCaseDetection } from '../lib/case-detection';

const DRAWER_WIDTH = 240;

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { currentCase, isDevMode } = useCaseDetection();

  // Define navigation items with case visibility
  const navigationItems = [
    {
      key: 'client',
      path: '/client',
      label: t('nav.client'),
      icon: <PersonIcon />,
      visibleInCases: [1, 2, 3, 4, 5],
      stepIndex: 0,
    },
    {
      key: 'currentEmployer',
      path: '/employer-current',
      label: t('nav.currentEmployer'),
      icon: <WorkIcon />,
      visibleInCases: [5], // Only visible in Case 5
      stepIndex: 1,
    },
    {
      key: 'pastEmployers',
      path: '/employers-past',
      label: t('nav.pastEmployers'),
      icon: <HistoryIcon />,
      visibleInCases: [1, 2, 3, 4, 5],
      stepIndex: 2,
    },
    {
      key: 'pensions',
      path: '/pensions',
      label: t('nav.pensions'),
      icon: <PensionIcon />,
      visibleInCases: [1, 2, 3, 4, 5],
      stepIndex: 3,
    },
    {
      key: 'incomeAssets',
      path: '/income-assets',
      label: t('nav.incomeAssets'),
      icon: <MoneyIcon />,
      visibleInCases: [1, 2, 3, 4, 5],
      stepIndex: 4,
    },
    {
      key: 'taxAdmin',
      path: '/tax-admin',
      label: t('nav.taxAdmin'),
      icon: <SettingsIcon />,
      visibleInCases: [1, 2, 3, 4, 5],
      stepIndex: 5,
    },
    {
      key: 'scenarios',
      path: '/scenarios',
      label: t('nav.scenarios'),
      icon: <ScenariosIcon />,
      visibleInCases: [1, 2, 3, 4, 5],
      stepIndex: 6,
    },
    {
      key: 'results',
      path: '/results',
      label: t('nav.results'),
      icon: <ResultsIcon />,
      visibleInCases: [1, 2, 3, 4, 5],
      stepIndex: 7,
    },
  ];

  // Filter navigation items based on current case
  const visibleItems = navigationItems.filter(item =>
    item.visibleInCases.includes(currentCase)
  );

  // Get current step index
  const currentPath = location.pathname;
  const currentItem = visibleItems.find(item => item.path === currentPath);
  const activeStep = currentItem ? currentItem.stepIndex : 0;

  const handleNavigation = (path: string) => {
    navigate(path);
  };

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <Box sx={{ display: 'flex' }}>
      {/* Dev Mode Badge */}
      {isDevMode && (
        <Chip
          label={t('dev.mode')}
          color="warning"
          size="small"
          sx={{
            position: 'fixed',
            top: 10,
            left: 10,
            zIndex: 9999,
          }}
        />
      )}

      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: sidebarOpen ? `calc(100% - ${DRAWER_WIDTH}px)` : '100%',
          mr: sidebarOpen ? `${DRAWER_WIDTH}px` : 0,
          transition: 'width 0.3s ease, margin 0.3s ease',
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="toggle sidebar"
            onClick={toggleSidebar}
            edge="start"
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            מערכת תכנון פרישה
          </Typography>
          <Chip
            label={t(`case.${currentCase}`)}
            color="secondary"
            size="small"
            sx={{ ml: 2 }}
          />
        </Toolbar>
      </AppBar>

      {/* Sidebar */}
      <Drawer
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
          },
        }}
        variant="persistent"
        anchor="right"
        open={sidebarOpen}
      >
        <Toolbar />
        
        {/* Progress Stepper */}
        <Box sx={{ p: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            התקדמות בתהליך
          </Typography>
          <Stepper activeStep={activeStep} orientation="vertical">
            {visibleItems.map((item) => (
              <Step key={item.key}>
                <StepLabel>{item.label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>

        {/* Navigation List */}
        <List>
          {visibleItems.map((item) => (
            <ListItem key={item.key} disablePadding>
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => handleNavigation(item.path)}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: sidebarOpen ? `calc(100% - ${DRAWER_WIDTH}px)` : '100%',
          transition: 'width 0.3s ease',
        }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
};

export default Layout;
