import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get('token');
    if (token) {
      login(token);
      navigate('/dashboard');
    } else {
      navigate('/login');
    }
  }, [searchParams, login, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="text-center space-y-4">
        <div className="animate-spin material-symbols-outlined text-4xl text-primary font-bold">
          progress_activity
        </div>
        <p className="font-headline font-semibold text-on-surface-variant">
          Securing your session...
        </p>
      </div>
    </div>
  );
};

export default AuthCallback;
