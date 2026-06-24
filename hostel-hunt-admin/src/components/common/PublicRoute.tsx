import React from 'react';

interface PublicRouteProps {
  children: React.ReactNode;
}

export const PublicRoute: React.FC<PublicRouteProps> = ({ children }) => {
  // Placeholder: Authentication logic removed
  // Will be connected to Python backend later
  return <>{children}</>;
};
