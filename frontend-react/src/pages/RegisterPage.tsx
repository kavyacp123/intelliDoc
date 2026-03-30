import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Input } from '../components/ui';

const RegisterPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [company, setCompany] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsLoading(true);

    try {
      const res = await fetch('http://localhost:8000/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          email, 
          password,
          full_name: fullName,
          company: company
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || 'Registration failed. Please try again.');
        setIsLoading(false);
        return;
      }

      setSuccess('Account created! Redirecting to login...');
      setTimeout(() => {
        navigate('/login');
      }, 1500);
    } catch (err) {
      setError('Could not connect to server. Is the backend running?');
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-background font-body">
      <header className="bg-slate-50 flex justify-center items-center w-full px-6 py-8">
        <span className="font-headline tracking-tighter text-3xl font-extrabold text-slate-900">intelliDoc</span>
      </header>

      <main className="flex-grow flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-xl">
          <div className="bg-surface-container-lowest p-8 md:p-12 rounded-xl shadow-atmospheric relative overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 primary-gradient"></div>
            <div className="mb-10">
              <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface mb-2">Create your account</h1>
              <p className="text-on-surface-variant text-sm">Join the network of elite financial professionals securing data intelligence.</p>
            </div>

            {error && (
              <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm font-medium animate-in fade-in slide-in-from-top-1">
                {error}
              </div>
            )}

            {success && (
              <div className="mb-4 px-4 py-3 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm font-medium animate-in fade-in slide-in-from-top-1">
                {success}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Input
                  label="Full Name"
                  placeholder="Johnathan Doe"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
                <Input
                  label="Company Name"
                  placeholder="Global Ledger Partners"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
              </div>

              <Input
                label="Work Email"
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              <div className="space-y-2">
                <Input
                  label="Password"
                  type="password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <div className="flex items-center gap-2 mt-2 px-1">
                  <span className="material-symbols-outlined text-[14px] text-secondary">info</span>
                  <span className="text-[11px] text-on-surface-variant font-medium">Password must be at least 8 characters</span>
                </div>
              </div>

              <div className="flex items-start gap-3 py-2 px-1">
                <div className="pt-0.5">
                  <input className="w-4 h-4 rounded border-outline-variant text-secondary focus:ring-secondary" id="tos" type="checkbox" required/>
                </div>
                <label className="text-xs text-on-surface-variant leading-relaxed" htmlFor="tos">
                  I agree to the <a className="text-secondary hover:underline" href="#">Terms of Service</a> and <a className="text-secondary hover:underline" href="#">Privacy Policy</a>
                </label>
              </div>

              <div className="space-y-4 pt-4">
                <Button type="submit" isLoading={isLoading} className="w-full py-4 group">
                  <span>Create Account</span>
                  <span className="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">arrow_forward</span>
                </Button>
                <div className="text-center pt-2">
                  <p className="text-sm text-on-surface-variant">
                    Already have an account? 
                    <Link to="/login" className="text-primary font-bold hover:text-secondary transition-colors px-1">Log in</Link>
                  </p>
                </div>
              </div>
            </form>
          </div>

          <div className="mt-12 flex flex-wrap justify-center items-center gap-8 opacity-40 grayscale hover:grayscale-0 hover:opacity-100 transition-all">
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-xl">verified_user</span>
              <span className="text-[10px] font-bold tracking-tighter uppercase">SOC2 Certified</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-xl">encrypted</span>
              <span className="text-[10px] font-bold tracking-tighter uppercase">AES-256 Encrypted</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-xl">account_balance</span>
              <span className="text-[10px] font-bold tracking-tighter uppercase">SEC Compliant</span>
            </div>
          </div>
        </div>
      </main>

      <footer className="bg-slate-50 border-t border-slate-200/10">
        <div className="w-full py-8 px-6 flex flex-col md:flex-row justify-between items-center gap-4 max-w-7xl mx-auto">
          <div className="font-headline font-semibold text-slate-400">intelliDoc</div>
          <div className="flex flex-wrap justify-center gap-6">
            <a href="#" className="text-xs text-slate-500 hover:text-secondary transition-colors">Privacy Policy</a>
            <a href="#" className="text-xs text-slate-500 hover:text-secondary transition-colors">Terms of Service</a>
            <a href="#" className="text-xs text-slate-500 hover:text-secondary transition-colors">Security Architecture</a>
          </div>
          <div className="text-xs text-slate-400">© 2024 intelliDoc Financial Intelligence.</div>
        </div>
      </footer>
    </div>
  );
};

export default RegisterPage;
