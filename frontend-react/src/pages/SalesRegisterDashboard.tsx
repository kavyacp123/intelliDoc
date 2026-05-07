import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Sidebar } from '../components/dashboard/Sidebar';
import { Button } from '../components/ui';
import { DataTable } from '../components/dashboard/DataTable';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from 'recharts';

type SummaryCard = {
  label: string;
  value: number;
  format: 'currency' | 'number' | 'days';
};

type DashboardQuery = {
  id: string;
  title: string;
  description: string;
  chart_type: 'bar' | 'line';
  label_key: string;
  value_key: string;
  secondary_value_key?: string;
  sql: string;
  data: any[];
  row_count: number;
};

type DashboardPayload = {
  title: string;
  notes: string[];
  summary_cards: SummaryCard[];
  queries: DashboardQuery[];
};

const CHART_COLORS = ['#bf6a02', '#e7a735', '#4f46e5', '#2563eb', '#0f766e', '#be123c', '#7c3aed', '#0891b2'];

const SalesRegisterDashboard: React.FC = () => {
  const { token, logout } = useAuth();
  const [datasets, setDatasets] = useState<any[]>([]);
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [exportingId, setExportingId] = useState<string | null>(null);

  const authHeaders = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  useEffect(() => {
    void loadDatasets();
  }, []);

  useEffect(() => {
    if (activeDatasetId) {
      void loadDashboard(activeDatasetId);
    }
  }, [activeDatasetId]);

  const loadDatasets = async () => {
    try {
      const res = await fetch('http://localhost:8000/datasets', { headers: authHeaders });
      const data = await res.json();
      if (res.ok && Array.isArray(data)) {
        const unique: any[] = [];
        const seen = new Set();
        for (const item of data) {
          if (!seen.has(item.file_name)) {
            seen.add(item.file_name);
            unique.push(item);
          }
        }
        setDatasets(unique);
        if (!activeDatasetId && unique.length > 0) {
          setActiveDatasetId(unique[0].dataset_id);
        }
      }
    } catch (err) {
      console.error('Failed to load datasets', err);
    }
  };

  const loadDashboard = async (datasetId: string) => {
    setIsLoading(true);
    setDashboardData(null);
    try {
      const res = await fetch('http://localhost:8000/dashboard/sales-register', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: datasetId }),
      });
      const data = await res.json();
      if (res.ok) {
        setDashboardData(data);
      } else {
        console.error(data);
      }
    } catch (err) {
      console.error('Failed to load sales register dashboard', err);
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
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        await loadDatasets();
        setActiveDatasetId(data.dataset_id);
      }
    } catch (err) {
      console.error('Upload failed', err);
      alert('Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteDataset = async (id: string) => {
    if (!window.confirm('Delete this dataset permanently?')) return;
    try {
      const res = await fetch(`http://localhost:8000/datasets/${id}`, {
        method: 'DELETE',
        headers: authHeaders,
      });
      if (res.ok) {
        setDatasets((prev) => {
          const next = prev.filter((item) => item.dataset_id !== id);
          if (activeDatasetId === id) {
            setActiveDatasetId(next.length > 0 ? next[0].dataset_id : null);
          }
          return next;
        });
      }
    } catch (err) {
      console.error('Delete failed', err);
      alert('Delete failed');
    }
  };

  const downloadWorkbook = async (queryId?: string) => {
    if (!activeDatasetId) return;
    setExportingId(queryId || 'all');
    try {
      const params = new URLSearchParams({ dataset_id: activeDatasetId });
      if (queryId) {
        params.set('query_id', queryId);
      }
      const res = await fetch(`http://localhost:8000/dashboard/sales-register/export?${params.toString()}`, {
        headers: authHeaders,
      });
      if (!res.ok) {
        throw new Error('Export failed');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = queryId ? `${queryId}.xlsx` : 'sales_register_dashboard.xlsx';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert('Export failed');
    } finally {
      setExportingId(null);
    }
  };

  const formatMetric = (value: number, format: SummaryCard['format']) => {
    if (format === 'currency') {
      if (Math.abs(value) >= 1_000_000) return `₹${(value / 1_000_000).toFixed(2)}M`;
      if (Math.abs(value) >= 1_000) return `₹${(value / 1_000).toFixed(1)}K`;
      return `₹${value.toLocaleString()}`;
    }
    if (format === 'days') return `${value.toFixed(1)} days`;
    return value.toLocaleString();
  };

  const formatAxisValue = (value: any) => {
    if (typeof value !== 'number') return String(value);
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toFixed(0);
  };

  const renderChart = (query: DashboardQuery) => {
    if (!query.data || query.data.length === 0) {
      return (
        <div className="h-72 flex items-center justify-center text-sm text-amber-900/60">
          No rows returned for this query.
        </div>
      );
    }

    const chartData = query.data.slice(0, 12).map((row) => ({
      label: String(row[query.label_key] ?? ''),
      primary: Number(row[query.value_key] ?? 0),
      secondary: query.secondary_value_key ? Number(row[query.secondary_value_key] ?? 0) : undefined,
    }));

    if (query.chart_type === 'line') {
      return (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eadfc5" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#7c5f2e' }} />
            <YAxis tick={{ fontSize: 11, fill: '#7c5f2e' }} tickFormatter={formatAxisValue} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="primary" name={query.value_key} stroke="#bf6a02" strokeWidth={3} dot={{ r: 4 }} />
            {query.secondary_value_key && (
              <Line type="monotone" dataKey="secondary" name={query.secondary_value_key} stroke="#2563eb" strokeWidth={3} dot={{ r: 4 }} />
            )}
          </LineChart>
        </ResponsiveContainer>
      );
    }

    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eadfc5" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: '#7c5f2e' }}
            interval={0}
            angle={chartData.length > 6 ? -24 : 0}
            textAnchor={chartData.length > 6 ? 'end' : 'middle'}
            height={chartData.length > 6 ? 72 : 36}
          />
          <YAxis tick={{ fontSize: 11, fill: '#7c5f2e' }} tickFormatter={formatAxisValue} />
          <Tooltip />
          <Bar dataKey="primary" radius={[8, 8, 0, 0]}>
            {chartData.map((_, index) => (
              <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  };

  return (
    <div className="flex h-screen bg-[radial-gradient(circle_at_top,_#fff6dc,_#f4ead2_45%,_#eadbc2_100%)] overflow-hidden">
      <Sidebar
        datasets={datasets}
        activeId={activeDatasetId}
        onSelect={setActiveDatasetId}
        onUpload={handleUpload}
        onDelete={handleDeleteDataset}
        isUploading={isUploading}
      />

      <main className="flex-1 overflow-y-auto">
        <header className="sticky top-0 z-40 border-b border-amber-900/10 bg-[#fff7e6]/85 backdrop-blur-xl px-8 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.32em] text-amber-900/55 font-bold">Commercial Intelligence Ledger</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-[#3b2413]" style={{ fontFamily: 'Georgia, Times New Roman, serif' }}>
                Sales Register Command Deck
              </h1>
              <p className="mt-2 max-w-3xl text-sm text-amber-950/70">
                Ten precomputed business queries, visual trend blocks, and workbook export for structured sales-register datasets.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={() => void downloadWorkbook()}
                isLoading={exportingId === 'all'}
                className="bg-[#3b2413] text-[#fff7e6] hover:opacity-95"
              >
                <span className="material-symbols-outlined text-sm">download</span>
                Export Full Workbook
              </Button>
              <Button variant="secondary" onClick={() => { window.location.href = '/dashboard'; }} className="bg-white/70">
                Switch to AI Chat
              </Button>
              <Button variant="ghost" onClick={logout} className="text-amber-900">Logout</Button>
            </div>
          </div>
        </header>

        {isLoading ? (
          <div className="h-[80vh] flex flex-col items-center justify-center gap-4 text-[#5d4323]">
            <span className="material-symbols-outlined animate-spin text-5xl">progress_activity</span>
            <p className="text-sm uppercase tracking-[0.22em]">Compiling 10 prebuilt analytics blocks...</p>
          </div>
        ) : dashboardData ? (
          <div className="px-8 py-8 pb-20 space-y-8">
            <section className="grid grid-cols-2 gap-4 xl:grid-cols-5">
              {dashboardData.summary_cards.map((card) => (
                <div
                  key={card.label}
                  className="rounded-[24px] border border-amber-900/10 bg-white/75 px-5 py-5 shadow-[0_20px_50px_rgba(125,89,32,0.08)] backdrop-blur"
                >
                  <p className="text-[11px] uppercase tracking-[0.22em] text-amber-900/45 font-bold">{card.label}</p>
                  <p className="mt-3 text-3xl font-black text-[#3b2413]">{formatMetric(card.value, card.format)}</p>
                </div>
              ))}
            </section>

            <section className="rounded-[28px] border border-amber-900/10 bg-[#fffaf0]/80 p-6 shadow-[0_20px_50px_rgba(125,89,32,0.06)]">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-[#3b2413] text-[#fff7e6] flex items-center justify-center">
                  <span className="material-symbols-outlined">rule</span>
                </div>
                <div>
                  <h2 className="text-lg font-black text-[#3b2413]">Interpretation Notes</h2>
                  <p className="text-sm text-amber-950/65">A few queries use robust fallbacks when the source sales register does not contain supplier or receipt ledgers.</p>
                </div>
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {dashboardData.notes.map((note, index) => (
                  <div key={index} className="rounded-2xl border border-amber-900/10 bg-white/80 px-4 py-3 text-sm text-amber-950/75">
                    {note}
                  </div>
                ))}
              </div>
            </section>

            <section className="grid gap-6 2xl:grid-cols-2">
              {dashboardData.queries.map((query, index) => (
                <article
                  key={query.id}
                  className="overflow-hidden rounded-[30px] border border-amber-900/10 bg-white/80 shadow-[0_25px_60px_rgba(78,54,19,0.10)]"
                >
                  <div className="border-b border-amber-900/10 bg-[linear-gradient(135deg,_rgba(59,36,19,0.96),_rgba(126,83,21,0.96))] px-6 py-5 text-[#fff7e6]">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.28em] text-amber-100/60 font-bold">Query {index + 1}</p>
                        <h3 className="mt-2 text-xl font-black leading-tight">{query.title}</h3>
                        <p className="mt-2 text-sm text-amber-50/78 max-w-2xl">{query.description}</p>
                      </div>
                      <Button
                        onClick={() => void downloadWorkbook(query.id)}
                        isLoading={exportingId === query.id}
                        className="bg-white/10 px-4 py-2 text-xs text-[#fff7e6] hover:bg-white/20"
                      >
                        <span className="material-symbols-outlined text-sm">download</span>
                        Excel
                      </Button>
                    </div>
                  </div>

                  <div className="p-6 space-y-6">
                    <div className="rounded-[24px] border border-amber-900/10 bg-[#fffaf0] p-4">
                      {renderChart(query)}
                    </div>

                    <div className="rounded-[24px] border border-amber-900/10 bg-white p-2">
                      <DataTable data={query.data} rowCount={query.row_count} />
                    </div>

                    <details className="rounded-[20px] border border-amber-900/10 bg-[#fdf7eb] p-4">
                      <summary className="cursor-pointer text-sm font-bold text-[#6f4a1f]">View SQL</summary>
                      <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-[11px] leading-relaxed text-amber-950/70">{query.sql}</pre>
                    </details>
                  </div>
                </article>
              ))}
            </section>
          </div>
        ) : (
          <div className="h-[80vh] flex flex-col items-center justify-center gap-4 px-8 text-center text-amber-950/65">
            <span className="material-symbols-outlined text-6xl text-amber-900/25">finance_mode</span>
            <h2 className="text-2xl font-black text-[#3b2413]">No compatible sales-register dataset selected</h2>
            <p className="max-w-xl text-sm">Upload a flattened sales register or select an existing one to load the 10 prebuilt analytics queries.</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default SalesRegisterDashboard;
