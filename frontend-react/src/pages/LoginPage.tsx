import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Input } from '../components/ui';

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    const body = new URLSearchParams();
    body.append('username', email);
    body.append('password', password);

    try {
      const res = await fetch('http://localhost:8000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || 'Invalid email or password.');
        setIsLoading(false);
        return;
      }

      login(data.access_token);
      navigate('/dashboard');
    } catch (err) {
      setError('Could not connect to server. Is the backend running?');
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-surface font-body">
      <header className="w-full py-8 px-6 max-w-7xl mx-auto flex justify-center md:justify-start items-center">
        <span className="text-2xl font-headline font-extrabold tracking-tighter text-primary">intelliDoc</span>
      </header>

      <main className="flex-grow flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="bg-surface-container-lowest shadow-atmospheric rounded-xl p-8 md:p-10 border border-outline-variant/10">
            <div className="mb-10 text-center md:text-left">
              <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface mb-2">Welcome Back</h1>
              <p className="text-on-surface-variant text-sm font-medium">Please enter your details to access your intelligence dashboard.</p>
            </div>

            {error && (
              <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm font-medium animate-in fade-in slide-in-from-top-1">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <Input
                label="Email Address"
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="block text-[10px] font-bold uppercase tracking-widest text-on-surface-variant px-1">Password</label>
                  <Button variant="ghost" className="text-xs p-0 h-auto">Forgot password?</Button>
                </div>
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <div className="flex items-center gap-2">
                <input className="w-4 h-4 rounded-sm border-outline-variant text-primary focus:ring-primary transition-all" id="remember" type="checkbox"/>
                <label className="text-sm font-medium text-on-surface-variant" htmlFor="remember">Remember me for 30 days</label>
              </div>

              <Button type="submit" isLoading={isLoading} className="w-full py-4">
                <span>Sign In</span>
                <span className="material-symbols-outlined text-[20px]">login</span>
              </Button>

              <div className="relative flex items-center gap-4 py-2">
                <div className="h-px w-full bg-outline-variant/20"></div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant whitespace-nowrap">OR</span>
                <div className="h-px w-full bg-outline-variant/20"></div>
              </div>

              <Button 
                type="button" 
                variant="secondary" 
                className="w-full py-4 flex items-center justify-center gap-3 border border-outline-variant/30"
                onClick={() => window.location.href = 'http://localhost:8000/auth/google'}
              >
                <img src="https://www.gstatic.com/images/branding/product/1x/gsuite_512dp.png" alt="Google" className="w-5 h-5" />
                <span>Continue with Google</span>
              </Button>
            </form>

            <div className="mt-8 pt-8 border-t border-outline-variant/15 text-center">
              <p className="text-sm text-on-surface-variant font-medium">
                Don't have an account? 
                <Link to="/register" className="text-secondary font-bold hover:underline ml-1">Sign up</Link>
              </p>
            </div>
          </div>

          <div className="mt-8 flex items-center justify-center gap-4 opacity-40">
            <div className="flex items-center gap-1.5 px-3 py-1 bg-surface-container border border-outline-variant/10 rounded-full">
              <span className="material-symbols-outlined text-[16px] fill-current">lock</span>
              <span className="text-[10px] font-bold uppercase tracking-widest">256-bit AES</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1 bg-surface-container border border-outline-variant/10 rounded-full">
              <span className="material-symbols-outlined text-[16px] fill-current">verified_user</span>
              <span className="text-[10px] font-bold uppercase tracking-widest">ISO 27001</span>
            </div>
          </div>
        </div>
      </main>

      <footer className="w-full py-8 px-6 flex flex-col md:flex-row justify-between items-center gap-4 max-w-7xl mx-auto border-t border-slate-200/10">
        <div className="font-headline font-semibold text-slate-400">intelliDoc</div>
        <div className="flex flex-wrap justify-center gap-6">
          <a href="#" className="text-xs text-slate-500 hover:text-secondary transition-colors">Privacy Policy</a>
          <a href="#" className="text-xs text-slate-500 hover:text-secondary transition-colors">Terms of Service</a>
          <a href="#" className="text-xs text-slate-500 hover:text-secondary transition-colors">Security Architecture</a>
        </div>
        <div className="text-xs text-slate-400">© 2024 intelliDoc Financial Intelligence.</div>
      </footer>
    </div>
  );
};

export default LoginPage;
