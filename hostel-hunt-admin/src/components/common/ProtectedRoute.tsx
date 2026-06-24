import React from 'react';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  // Placeholder: Authentication logic removed
  // Will be connected to Python backend later
  return <>{children}</>;
};
