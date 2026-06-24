import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './pages/auth/LoginPage';
import { SignupPage } from './pages/auth/SignupPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { EditHostelPage } from './pages/hostel/EditHostelPage';
import { BookingsPage } from './pages/bookings/BookingsPage';
import { PaymentsPage } from './pages/payments/PaymentsPage';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { PublicRoute } from './components/common/PublicRoute';
import { UsersPage } from './pages/users/UsersPage';

// Placeholder for pages not yet built
const PlaceholderPage = ({ title }: { title: string }) => (
  <div className="min-h-screen bg-[#0F0F0F] flex items-center justify-center p-4 text-[#F0EDE8]">
    <div className="bg-[#1A1A1A] rounded-xl border border-[#2A2A2A] p-10 max-w-md w-full text-center">
      <div className="text-4xl mb-4">🚧</div>
      <h2 className="text-2xl font-bold mb-2">{title}</h2>
      <p className="text-[#9A9690] mb-6">Coming in the next phase.</p>
      <button onClick={() => window.history.back()}
        className="text-[#E8571A] hover:text-[#FF6B35] font-semibold transition-colors">
        ← Go Back
      </button>
    </div>
  </div>
);

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Root redirect */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Public routes */}
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/signup" element={<PublicRoute><SignupPage /></PublicRoute>} />
        <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />

        {/* Protected routes */}
        <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/hostel" element={<ProtectedRoute><PlaceholderPage title="My Hostel" /></ProtectedRoute>} />
        <Route path="/hostel/edit" element={<ProtectedRoute><EditHostelPage /></ProtectedRoute>} />
        <Route path="/rooms" element={<ProtectedRoute><PlaceholderPage title="Rooms" /></ProtectedRoute>} />
        <Route path="/bookings" element={<ProtectedRoute><BookingsPage /></ProtectedRoute>} />
        <Route path="/payments" element={<ProtectedRoute><PaymentsPage /></ProtectedRoute>} />
        <Route path="/users" element={<ProtectedRoute><UsersPage /></ProtectedRoute>} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
