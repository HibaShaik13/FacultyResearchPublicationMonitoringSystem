import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function ProtectedRoute() {
  const { user, token, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-surface-950)' }}>
        <div className="animate-pulse flex flex-col items-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
          <p style={{ color: 'var(--color-text-secondary)' }}>Loading VFSTR Research Platform...</p>
        </div>
      </div>
    );
  }

  if (!token || (!user && !loading)) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
