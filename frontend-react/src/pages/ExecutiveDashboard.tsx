import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Sidebar } from '../components/dashboard/Sidebar';
import { Button } from '../components/ui';
import { DataTable } from '../components/dashboard/DataTable';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell
} from 'recharts';

// ─── Color palette ───
const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];
const KPI_GRADIENTS: Record<string, string> = {
  emerald: 'from-emerald-500 to-emerald-700',
  red: 'from-rose-500 to-rose-700',
  blue: 'from-blue-500 to-blue-700',
  violet: 'from-violet-500 to-violet-700',
  amber: 'from-amber-500 to-amber-600',
  slate: 'from-slate-600 to-slate-800',
};

interface KPI {
  name: string;
  value: string;
  raw_value: number;
  icon: string;
  color: string;
  type: string;
}

interface Section {
  title: string;
  chart_type: string;
  icon: string;
  data: any[];
  x_key: string;
  y_key: string;
  color: string;
}

interface PredefinedQuery {
  name: string;
  description: string;
  sql: string;
  icon: string;
}

interface DashboardData {
  kpis: KPI[];
  sections: Section[];
  predefined_queries: PredefinedQuery[];
  insight_button: { enabled: boolean; label: string };
  notes: string[];
  detected_fields: Record<string, any>;
}

const ExecutiveDashboard: React.FC = () => {
  const { token, logout } = useAuth();
  const [datasets, setDatasets] = useState<any[]>([]);
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  // AI Insights State
  const [aiInsights, setAiInsights] = useState<any>(null);
  const [isInsightsLoading, setIsInsightsLoading] = useState(false);

  // Predefined query execution state
  const [activeQuery, setActiveQuery] = useState<PredefinedQuery | null>(null);
  const [queryResult, setQueryResult] = useState<any[] | null>(null);
  const [isQueryLoading, setIsQueryLoading] = useState(false);

  const authHeaders = { 'Authorization': `Bearer ${token}` };

  useEffect(() => { loadDatasets(); }, []);
  useEffect(() => {
    if (activeDatasetId) loadDashboard(activeDatasetId);
  }, [activeDatasetId]);

  const loadDatasets = async () => {
    try {
      const res = await fetch('http://localhost:8000/datasets', { headers: authHeaders });
      const data = await res.json();
      if (res.ok && data.length > 0) {
        const unique: any[] = [];
        const seen = new Set();
        for (const d of data) {
          if (!seen.has(d.file_name)) { seen.add(d.file_name); unique.push(d); }
        }
        setDatasets(unique);
        if (!activeDatasetId) setActiveDatasetId(unique[0].dataset_id);
      }
    } catch (err) { console.error('Failed to load datasets', err); }
  };

  const loadDashboard = async (id: string) => {
    setIsLoading(true);
    setDashboardData(null);
    setActiveQuery(null);
    setQueryResult(null);
    setAiInsights(null); // Clear insights when switching datasets
    try {
      const res = await fetch('http://localhost:8000/dashboard/executive', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: id }),
      });
      const data = await res.json();
      if (res.ok) setDashboardData(data);
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
        method: 'POST', headers: authHeaders, body: formData,
      });
      const data = await res.json();
      if (res.ok) { await loadDatasets(); setActiveDatasetId(data.dataset_id); }
    } catch { alert('Upload failed'); }
    finally { setIsUploading(false); }
  };

  const handleDeleteDataset = async (id: string) => {
    if (!window.confirm('Delete this dataset permanently?')) return;
    try {
      const res = await fetch(`http://localhost:8000/datasets/${id}`, {
        method: 'DELETE', headers: authHeaders,
      });
      if (res.ok) {
        setDatasets(prev => {
          const next = prev.filter(d => d.dataset_id !== id);
          if (activeDatasetId === id) setActiveDatasetId(next.length > 0 ? next[0].dataset_id : null);
          return next;
        });
      }
    } catch { alert('Delete failed'); }
  };

  const runPredefinedQuery = async (query: PredefinedQuery) => {
    setActiveQuery(query);
    setQueryResult(null);
    setIsQueryLoading(true);
    try {
      const res = await fetch('http://localhost:8000/dashboard/executive/query', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: query.sql, dataset_id: activeDatasetId }),
      });
      const data = await res.json();
      if (res.ok) setQueryResult(data.data);
    } catch (err) { console.error('Query failed', err); }
    finally { setIsQueryLoading(false); }
  };

  const executeGenerateInsights = async () => {
    if (!dashboardData) return;
    setIsInsightsLoading(true);
    try {
      const res = await fetch('http://localhost:8000/dashboard/executive/insights', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ dashboard_data: dashboardData }),
      });
      const data = await res.json();
      if (res.ok) setAiInsights(data);
    } catch (err) { console.error('Insight generation failed', err); }
    finally { setIsInsightsLoading(false); }
  };

  const formatValue = (val: any): string => {
    if (typeof val === 'number') {
      if (Math.abs(val) >= 1_000_000) return `₹${(val / 1_000_000).toFixed(2)}M`;
      if (Math.abs(val) >= 1_000) return `₹${(val / 1_000).toFixed(1)}K`;
      return val.toLocaleString();
    }
    return String(val);
  };

  // Custom Tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload?.length) {
      return (
        <div className="bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl text-xs border border-slate-700">
          <p className="font-bold mb-1 text-slate-300">{label}</p>
          {payload.map((p: any, i: number) => (
            <p key={i} className="flex justify-between gap-4">
              <span style={{ color: p.color }}>{p.name}:</span>
              <span className="font-mono font-bold">{formatValue(p.value)}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  // ─── Chart Renderer ───
  const renderSectionChart = (section: Section) => {
    const chartData = section.data.map(row => ({
      name: String(row[section.x_key] ?? ''),
      value: Number(row[section.y_key] ?? 0),
    }));

    if (section.chart_type === 'line') {
      return (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.4} />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#94a3b8' }} dy={10} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={v => formatValue(v)} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey="value" stroke={section.color} strokeWidth={3}
              dot={{ r: 4, fill: '#fff', stroke: section.color, strokeWidth: 2 }}
              activeDot={{ r: 6, strokeWidth: 0, fill: section.color }} />
          </LineChart>
        </ResponsiveContainer>
      );
    }

    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.4} />
          <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#94a3b8' }} dy={10}
            interval={0} angle={chartData.length > 6 ? -30 : 0} textAnchor={chartData.length > 6 ? "end" : "middle"} />
          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={v => formatValue(v)} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
          <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={36}>
            {chartData.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  };

  // ─── RENDER ───
  return (
    <div className="flex h-screen bg-[#f8fafc] overflow-hidden">
      <Sidebar
        datasets={datasets}
        activeId={activeDatasetId}
        onSelect={setActiveDatasetId}
        onUpload={handleUpload}
        onDelete={handleDeleteDataset}
        isUploading={isUploading}
      />

      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <header className="sticky top-0 z-40 backdrop-blur-xl bg-white/80 border-b border-slate-100 px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 font-headline tracking-tight flex items-center gap-2">
              <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>monitoring</span>
              Executive Dashboard
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">Auto-generated financial analytics • Zero-click</p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="secondary" onClick={() => window.location.href = '/dashboard'} className="text-xs">
              Switch to AI Chat
            </Button>
            <Button variant="ghost" onClick={logout} className="text-xs">Logout</Button>
          </div>
        </header>

        {isLoading ? (
          <div className="h-[80vh] flex flex-col items-center justify-center gap-4">
            <span className="animate-spin material-symbols-outlined text-5xl text-primary">progress_activity</span>
            <p className="text-sm text-slate-500 font-medium animate-pulse">Building your executive dashboard...</p>
          </div>
        ) : dashboardData ? (
          <div className="px-8 py-6 space-y-8 pb-20">

            {/* ── KPI Hero Cards ── */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {dashboardData.kpis.map((kpi, i) => (
                <div
                  key={i}
                  className={`relative overflow-hidden rounded-2xl p-5 text-white shadow-lg bg-gradient-to-br ${KPI_GRADIENTS[kpi.color] || KPI_GRADIENTS.slate} transition-transform hover:scale-[1.02]`}
                >
                  <div className="absolute top-3 right-3 opacity-20">
                    <span className="material-symbols-outlined text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>{kpi.icon}</span>
                  </div>
                  <p className="text-[10px] font-bold uppercase tracking-widest opacity-80 mb-2">{kpi.name}</p>
                  <p className="text-2xl font-extrabold tracking-tight truncate">{kpi.value}</p>
                </div>
              ))}
            </div>

            {/* ── Chart Sections ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {dashboardData.sections.map((section, i) => (
                <div
                  key={i}
                  className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow"
                >
                  <div className="px-6 py-4 border-b border-slate-50 flex items-center gap-2">
                    <span className="material-symbols-outlined text-lg text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
                      {section.icon}
                    </span>
                    <h3 className="text-sm font-bold text-slate-800 tracking-tight">{section.title}</h3>
                    <span className="ml-auto text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider">
                      {section.chart_type}
                    </span>
                  </div>
                  <div className="p-6">
                    {renderSectionChart(section)}
                  </div>
                </div>
              ))}
            </div>

            {/* ── Predefined Queries ── */}
            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-50 flex items-center gap-2">
                <span className="material-symbols-outlined text-lg text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>terminal</span>
                <h3 className="text-sm font-bold text-slate-800">Predefined Financial Queries</h3>
                <span className="ml-auto text-[10px] text-slate-400">Click any query to execute</span>
              </div>
              <div className="p-6">
                <div className="flex flex-wrap gap-2 mb-6">
                  {dashboardData.predefined_queries.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => runPredefinedQuery(q)}
                      className={`inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold border transition-all duration-200 active:scale-95 ${
                        activeQuery?.name === q.name
                          ? 'bg-primary text-white border-primary shadow-lg shadow-primary/20'
                          : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-primary/5 hover:border-primary/30 hover:text-primary'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>{q.icon}</span>
                      {q.name}
                    </button>
                  ))}
                </div>

                {/* Query Result */}
                {activeQuery && (
                  <div className="border border-slate-100 rounded-xl overflow-hidden animate-in slide-in-from-bottom-2 fade-in duration-300">
                    <div className="px-5 py-3 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-slate-800">{activeQuery.name}</h4>
                        <p className="text-[11px] text-slate-500">{activeQuery.description}</p>
                      </div>
                      <button onClick={() => { setActiveQuery(null); setQueryResult(null); }}
                        className="text-slate-400 hover:text-slate-600 transition-colors">
                        <span className="material-symbols-outlined text-lg">close</span>
                      </button>
                    </div>
                    <div className="bg-slate-900 px-5 py-3 border-b border-slate-800">
                      <pre className="text-emerald-400 text-[10px] font-mono leading-relaxed overflow-x-auto">{activeQuery.sql}</pre>
                    </div>
                    <div className="p-4">
                      {isQueryLoading ? (
                        <div className="flex items-center justify-center py-10">
                          <span className="animate-spin material-symbols-outlined text-2xl text-primary">progress_activity</span>
                        </div>
                      ) : queryResult ? (
                        <DataTable data={queryResult} rowCount={queryResult.length} />
                      ) : (
                        <p className="text-center text-slate-400 text-sm py-8">Click "Execute" to run this query</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
            {/* ── AI Insights Panel ── */}
            <div className="bg-gradient-to-br from-indigo-50 to-white rounded-2xl border border-indigo-100 shadow-sm overflow-hidden mt-8">
              <div className="px-6 py-4 border-b border-indigo-50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-lg text-indigo-600" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                  <h3 className="text-sm font-bold text-slate-800">Executive Briefing</h3>
                </div>
                {!aiInsights && !isInsightsLoading && (
                  <Button onClick={executeGenerateInsights} variant="primary" className="text-xs bg-indigo-600 hover:bg-indigo-700">
                    Generate AI Insights
                  </Button>
                )}
              </div>
              
              <div className="p-6">
                {isInsightsLoading ? (
                  <div className="flex flex-col items-center justify-center py-12 gap-3">
                    <span className="animate-spin material-symbols-outlined text-3xl text-indigo-600">sync</span>
                    <p className="text-sm text-indigo-600/70 font-medium animate-pulse">Analyzing dashboard data & trends...</p>
                  </div>
                ) : aiInsights ? (
                  <div className="space-y-6 animate-in slide-in-from-bottom-4 fade-in duration-500">
                    {/* Summary */}
                    <div className="bg-indigo-600 text-white p-5 rounded-xl">
                      <h4 className="text-[10px] font-bold uppercase tracking-widest text-indigo-200 mb-2">Executive Summary</h4>
                      <p className="text-sm leading-relaxed font-medium">{aiInsights.summary}</p>
                    </div>

                    {/* Key Insights Grid */}
                    <div>
                      <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-3 ml-1">Key Findings</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {aiInsights.insights?.map((insight: any, i: number) => (
                          <div key={i} className="bg-white border border-slate-100 p-4 rounded-xl shadow-sm">
                            <div className="flex items-center gap-2 mb-2">
                              <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                                insight.type === 'profitability' ? 'bg-emerald-100 text-emerald-700' :
                                insight.type === 'cost' ? 'bg-rose-100 text-rose-700' :
                                insight.type === 'risk' ? 'bg-amber-100 text-amber-700' :
                                'bg-blue-100 text-blue-700'
                              }`}>
                                {insight.type}
                              </span>
                              <span className="ml-auto text-[10px] text-slate-400 font-medium capitalize">{insight.confidence} confidence</span>
                            </div>
                            <h5 className="text-sm font-bold text-slate-800 mb-1">{insight.title}</h5>
                            <p className="text-xs text-slate-600 leading-relaxed">{insight.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Recommendations */}
                    {aiInsights.recommendations?.length > 0 && (
                      <div className="bg-emerald-50 border border-emerald-100 p-5 rounded-xl">
                        <h4 className="text-[10px] font-bold uppercase tracking-widest text-emerald-600 mb-3">Strategic Recommendations</h4>
                        <ul className="space-y-3">
                          {aiInsights.recommendations.map((rec: any, i: number) => (
                            <li key={i} className="flex items-start gap-3">
                              <span className="material-symbols-outlined text-[16px] text-emerald-600 mt-0.5">check_circle</span>
                              <div>
                                <p className="text-sm font-bold text-slate-800">{rec.action}</p>
                                <p className="text-xs text-slate-600">{rec.reason}</p>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-10">
                    <span className="material-symbols-outlined text-4xl text-slate-300 mb-2">query_stats</span>
                    <p className="text-slate-500 text-sm">Click the button above to generate a professional AI analysis of your data.</p>
                  </div>
                )}
              </div>
            </div>

            {/* ── Notes ── */}
            {dashboardData.notes.length > 0 && (
              <div className="bg-blue-50/50 rounded-xl border border-blue-100 px-6 py-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-sm text-blue-500">info</span>
                  <span className="text-[10px] font-bold uppercase tracking-widest text-blue-600">Dashboard Notes</span>
                </div>
                <ul className="space-y-1">
                  {dashboardData.notes.map((note, i) => (
                    <li key={i} className="text-xs text-blue-700/80 flex items-start gap-2">
                      <span className="text-blue-400 mt-1">•</span>
                      {note}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="h-[80vh] flex flex-col items-center justify-center gap-4">
            <span className="material-symbols-outlined text-6xl text-slate-300">monitoring</span>
            <h2 className="text-xl font-bold text-slate-400">No Dataset Selected</h2>
            <p className="text-sm text-slate-400">Upload or select a dataset to generate your executive dashboard.</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default ExecutiveDashboard;
