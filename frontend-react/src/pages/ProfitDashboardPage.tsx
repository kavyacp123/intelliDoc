import React, { useState } from 'react';
import axios from 'axios';
import { BarChart2, Activity, AlertCircle, FileJson } from 'lucide-react';
import { Button } from '../components/ui';
import { KPIGauge } from '../components/dashboard/KPIGauge';
import { GenericChart } from '../components/dashboard/GenericChart';
import { DataTable } from '../components/dashboard/DataTable';

interface DashboardData {
  kpis: any[];
  charts: any[];
  table: {
    columns: any[];
    rows: any[];
  };
}

const API_BASE_URL = 'http://localhost:8000';

export const ProfitDashboardPage: React.FC = () => {
  const [rawData, setRawData] = useState<string>('');
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!rawData.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const jsonData = JSON.parse(rawData);
      const token = localStorage.getItem('token');
      
      const response = await axios.post(`${API_BASE_URL}/dashboard/analyze`, {
        data: Array.isArray(jsonData) ? jsonData : [jsonData],
        dataset_name: "Manual Input"
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setDashboard(response.data);
    } catch (err: any) {
      setError(err.message || "Failed to parse JSON or analyze data");
    } finally {
      setLoading(false);
    }
  };

  const loadSampleData = () => {
    const sample = [
      { "Date": "2024-01-01", "Region": "North", "Sales": 12000, "Expense": 8000, "Units": 150 },
      { "Date": "2024-02-01", "Region": "South", "Sales": 15000, "Expense": 9500, "Units": 200 },
      { "Date": "2024-03-01", "Region": "North", "Sales": 18000, "Expense": 11000, "Units": 220 },
      { "Date": "2024-04-01", "Region": "West", "Sales": 22000, "Expense": 13000, "Units": 300 }
    ];
    setRawData(JSON.stringify(sample, null, 2));
  };

  return (
    <div className="min-h-screen bg-surface p-8 pb-24">
      <div className="max-w-7xl mx-auto space-y-12">
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3 text-primary">
              <Activity className="w-8 h-8" />
              <h1 className="text-3xl font-black tracking-tight uppercase">Profit Engine <span className="text-on-surface-variant font-light">V1</span></h1>
            </div>
            <p className="text-on-surface-variant max-w-lg">
              Input any JSON dataset. Our normalization engine will automatically map fields into financial KPIs and interactive visualizations.
            </p>
          </div>
          <div className="flex gap-3">
            <Button variant="ghost" onClick={loadSampleData} className="gap-2">
              <FileJson className="w-4 h-4" /> Load Sample
            </Button>
            <Button onClick={handleAnalyze} isLoading={loading} className="gap-2 min-w-[140px]">
              <BarChart2 className="w-4 h-4" /> Analyze Now
            </Button>
          </div>
        </header>

        {/* Input Area */}
        {!dashboard && (
          <section className="glass-panel p-8 rounded-3xl border border-outline-variant/50 animate-in fade-in slide-in-from-bottom-4">
             <div className="flex items-center gap-2 mb-4 text-on-surface font-bold truncate">
               <div className="w-2 h-6 bg-primary rounded-full" />
               Raw Dataset (JSON Array)
             </div>
             <textarea
                value={rawData}
                onChange={(e) => setRawData(e.target.value)}
                placeholder='[{"sales": 1000, "cost": 600, "date": "2024-01-01"}, ...]'
                className="w-full h-64 bg-surface-container-lowest border border-outline-variant rounded-xl p-4 font-mono text-sm focus:ring-2 focus:ring-primary/20 outline-hidden transition-all"
             />
             {error && (
               <div className="mt-4 p-4 bg-error-container/20 border border-error/20 rounded-xl flex items-center gap-3 text-error">
                 <AlertCircle className="w-5 h-5" />
                 <span className="text-sm font-medium">{error}</span>
               </div>
             )}
          </section>
        )}

        {/* Dynamic Dashboard Content */}
        {dashboard && (
          <div className="space-y-12 animate-in fade-in zoom-in-95 duration-500">
            {/* KPI Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {dashboard.kpis.map((kpi, i) => (
                <KPIGauge key={i} {...kpi} />
              ))}
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {dashboard.charts.map((chart, i) => (
                <GenericChart key={i} {...chart} />
              ))}
            </div>

            {/* Table Row */}
            <section className="space-y-4">
              <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-2 text-on-surface font-bold truncate">
                  <div className="w-2 h-6 bg-secondary rounded-full" />
                  Normalized Data Preview (Top 50)
                </div>
                <Button variant="ghost" onClick={() => setDashboard(null)}>Reset Analysis</Button>
              </div>
              <div className="glass-panel rounded-3xl overflow-hidden border border-outline-variant/30">
                <DataTable 
                  data={dashboard.table.rows} 
                  rowCount={dashboard.table.rows.length}
                />
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
};
