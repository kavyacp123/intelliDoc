import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AuthCallback from './pages/AuthCallback';
import DashboardPage from './pages/DashboardPage';
import { ProfitDashboardPage } from './pages/ProfitDashboardPage';
import ExecutiveDashboard from './pages/ExecutiveDashboard';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/auth-callback" element={<AuthCallback />} />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          } 
        />
        <Route
          path="/profit-engine"
          element={
            <ProtectedRoute>
              <ProfitDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/executive-dashboard"
          element={
            <ProtectedRoute>
              <ExecutiveDashboard />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
};

export default App;
