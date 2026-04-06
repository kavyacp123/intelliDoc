import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Sidebar } from '../components/dashboard/Sidebar';
import { Button } from '../components/ui';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer, Cell, PieChart, Pie 
} from 'recharts';

interface GaugeProps {
  label: string;
  value: number;
  color?: string;
}

const Gauge: React.FC<GaugeProps> = ({ label, value, color = "#0ea5e9" }) => {
  // Simple Gauge using PieChart
  const data = [
    { value: value },
    { value: 100 - value }
  ];

  return (
    <div className="flex flex-col items-center justify-center p-4 bg-white rounded-2xl shadow-atmospheric border border-outline-variant/10">
      <div className="relative w-32 h-32">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={35}
              outerRadius={50}
              startAngle={180}
              endAngle={0}
              paddingAngle={0}
              dataKey="value"
            >
              <Cell key="cell-0" fill={color} />
              <Cell key="cell-1" fill="#f1f5f9" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center pt-4">
          <span className="text-xl font-extrabold text-slate-800">{Math.round(value)}%</span>
        </div>
      </div>
      <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant text-center mt-[-10px]">
        {label}
      </span>
    </div>
  );
};

const ExecutiveDashboard: React.FC = () => {
  const { token, logout } = useAuth();
  const [datasets, setDatasets] = useState<any[]>([]);
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const authHeaders = { 'Authorization': `Bearer ${token}` };

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    if (activeDatasetId) {
      loadDashboard(activeDatasetId);
    }
  }, [activeDatasetId]);

  const loadDatasets = async () => {
    try {
      const res = await fetch('http://localhost:8000/datasets', { headers: authHeaders });
      const data = await res.json();
      if (res.ok && data.length > 0) {
        setDatasets(data);
        if (!activeDatasetId) setActiveDatasetId(data[0].dataset_id);
      }
    } catch (err) {
      console.error('Failed to load datasets', err);
    }
  };

  const loadDashboard = async (id: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/datasets/${id}/profit-dashboard`, { headers: authHeaders });
      const data = await res.json();
      if (res.ok) {
        setDashboardData(data);
      }
    } catch (err) {
      console.error('Failed to load dashboard', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    setIsUploading(true);
    try {
      const res = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        headers: authHeaders,
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        await loadDatasets();
        setActiveDatasetId(data.dataset_id);
      }
    } catch (err) {
      alert('Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'decimal',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(val);
  };

  if (!activeDatasetId) {
    return <div className="p-10 text-center">No datasets found. Please upload one first.</div>;
  }

  return (
    <div className="flex h-screen bg-[#f8fafc] overflow-hidden">
      <Sidebar 
        datasets={datasets} 
        activeId={activeDatasetId} 
        onSelect={setActiveDatasetId}
        onUpload={handleUpload}
        onDelete={() => {}}
        isUploading={isUploading}
      />

      <main className="flex-1 overflow-y-auto px-8 py-8 space-y-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 font-headline tracking-tight">Executive Profit Dashboard</h1>
            <p className="text-sm text-slate-500 font-medium">Real-time financial performance & profitability analysis</p>
          </div>
          <div className="flex items-center gap-3">
             <Button variant="secondary" onClick={() => window.location.href='/dashboard'}>Switch to AI Chat</Button>
             <Button variant="ghost" onClick={logout}>Logout</Button>
          </div>
        </header>

        {isLoading ? (
          <div className="h-96 flex items-center justify-center">
             <span className="animate-spin material-symbols-outlined text-4xl text-primary">progress_activity</span>
          </div>
        ) : dashboardData ? (
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 pb-20">
            
            {/* Top Gauges */}
            <div className="md:col-span-12 grid grid-cols-2 lg:grid-cols-4 gap-4">
              {dashboardData.gauges.map((g: any, i: number) => (
                <Gauge key={i} label={g.label} value={g.value} color={i % 2 === 0 ? "#0ea5e9" : "#3b82f6"} />
              ))}
            </div>

            {/* OPEX Trend */}
            <div className="md:col-span-7 bg-white p-6 rounded-2xl shadow- atmospheric border border-outline-variant/10">
              <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6">OPEX Detail <span className="text-[10px] lowercase font-normal opacity-60 ml-2">Month-to-Month | YTD</span></h3>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboardData.opex_chart}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '10px', fontWeight: 'bold' }} />
                    <Bar dataKey="Sales" stackId="a" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Marketing" stackId="a" fill="#60a5fa" />
                    <Bar dataKey="GA" stackId="a" fill="#93c5fd" />
                    <Line type="monotone" dataKey="OPEX_Ratio" stroke="#1e293b" strokeWidth={2} dot={{ r: 3 }} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Income Statement */}
            <div className="md:col-span-5 bg-white p-6 rounded-2xl shadow-atmospheric border border-outline-variant/10">
              <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6">Income Statement</h3>
              <div className="space-y-3">
                {dashboardData.statement.map((s: any, i: number) => (
                  <div key={i} className={`flex justify-between items-center py-2 ${s.isHeader ? 'border-t border-slate-100 pt-4 mt-4 font-bold text-slate-900' : 'text-slate-600 text-sm'}`}>
                    <span>{s.item}</span>
                    <span className="font-mono">{formatCurrency(s.value)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* EBIT Trend */}
            <div className="md:col-span-7 bg-white p-6 rounded-2xl shadow-atmospheric border border-outline-variant/10">
              <h3 className="text-sm font-bold uppercase tracking-widest text-slate-500 mb-6">Earnings before Interest and Taxes <span className="text-[10px] lowercase font-normal opacity-60 ml-2">Month-to-Month | YTD</span></h3>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dashboardData.ebit_chart}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }} />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '10px', fontWeight: 'bold' }} />
                    <Line type="monotone" dataKey="Actual" name="EBIT Actual" stroke="#0ea5e9" strokeWidth={3} dot={{ r: 4, fill: '#0ea5e9' }} />
                    <Line type="monotone" dataKey="Target" name="EBIT Target" stroke="#94a3b8" strokeDasharray="5 5" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

          </div>
        ) : (
          <div className="p-20 text-center text-slate-400">
             Could not analyze financial data for this dataset.
          </div>
        )}
      </main>
    </div>
  );
};

export default ExecutiveDashboard;
