import React from 'react';
import { DataTable } from './DataTable';
import { GenericChart } from './GenericChart';

interface SummaryCard {
  title: string;
  value: string;
  description: string;
}

interface KPICard {
  title: string;
  value: any;
  description: string;
}

interface ChartHint {
  type: string;
  x_axis?: string;
  y_axis?: string;
  series?: string;
  reason: string;
}

interface InsightPanel {
  type: string;
  text: string;
}

interface Anomaly {
  text: string;
  severity: string;
}

export interface DashboardInsights {
  summary_card: SummaryCard;
  kpi_cards: KPICard[];
  chart?: ChartHint;
  insights_panel: InsightPanel[];
  anomalies: Anomaly[];
}

interface DashboardPanelProps {
  insights: DashboardInsights;
  data: any[];
  rowCount: number;
}

export const DashboardPanel: React.FC<DashboardPanelProps> = ({ insights, data, rowCount }) => {
  return (
    <div className="flex flex-col gap-6 w-full">
      
      {/* 1. Summary Card (Hero Section) */}
      <div className="bg-gradient-to-br from-primary-container to-slate-900 rounded-2xl p-8 shadow-lg text-on-primary border border-outline-variant/20">
        <h2 className="text-sm font-semibold tracking-widest uppercase opacity-70 mb-2">Key Finding</h2>
        <h3 className="text-3xl font-headline font-bold mb-4">{insights.summary_card.title}</h3>
        <div className="flex items-end gap-3">
          <span className="text-4xl font-extrabold text-secondary-fixed">{insights.summary_card.value}</span>
        </div>
        <p className="mt-4 text-sm opacity-80 max-w-2xl">{insights.summary_card.description}</p>
      </div>

      {/* 2. KPI Metrics Grid */}
      {insights.kpi_cards && insights.kpi_cards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {insights.kpi_cards.map((kpi, idx) => (
            <div key={idx} className="bg-surface-container-lowest p-5 rounded-2xl border border-outline-variant/15 shadow-sm">
              <h4 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">{kpi.title}</h4>
              <p className="text-2xl font-bold text-on-surface tabular-nums truncate mb-1">{kpi.value}</p>
              <p className="text-[11px] text-on-surface-variant/70 leading-snug">{kpi.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* 3. Main Split: Chart + Insights */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Left Col: Chart & Table */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          {insights.chart && data && data.length > 0 && Array.isArray(data) && (
             <div className="bg-surface-container-lowest p-6 rounded-2xl border border-outline-variant/15 shadow-sm min-h-[400px] flex flex-col">
               <h4 className="text-sm font-bold text-on-surface mb-1 tracking-tight capitalize">{insights.chart.type} Analysis</h4>
               <p className="text-xs text-on-surface-variant/70 mb-6">{insights.chart.reason}</p>
               <div className="flex-1 w-full relative">
                 <GenericChart 
                    type={insights.chart.type === 'pie' || insights.chart.type === 'table' ? 'bar' : insights.chart.type}
                    title={insights.chart.reason}
                    x={data.map(d => String(d[insights.chart!.x_axis || Object.keys(d)[0]]))}
                    series={[{
                      name: insights.chart.y_axis || Object.keys(data[0])[1] || 'value',
                      data: data.map(d => Number(d[insights.chart!.y_axis || Object.keys(d)[1]]) || 0)
                    }]}
                 />
               </div>
             </div>
          )}
          
          <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 shadow-sm overflow-hidden">
             <div className="px-6 py-4 border-b border-outline-variant/10 bg-slate-50/50 flex justify-between items-center">
                 <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Underlying Data</span>
             </div>
             <DataTable data={data} rowCount={rowCount} />
          </div>
        </div>

        {/* Right Col: Deep Insights & Anomalies */}
        <div className="flex flex-col gap-6">
          
          {/* Business Insights */}
          <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/15 shadow-sm overflow-hidden">
             <div className="px-5 py-4 border-b border-outline-variant/10 bg-slate-50/50 flex items-center gap-2">
                 <span className="material-symbols-outlined text-[18px] text-secondary">analytics</span>
                 <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Business Impact</span>
             </div>
             <div className="p-5 flex flex-col gap-4">
                {insights.insights_panel && insights.insights_panel.length > 0 ? (
                  insights.insights_panel.map((ins, idx) => (
                    <div key={idx} className="flex gap-3 items-start">
                      <div className="w-6 h-6 rounded-full bg-secondary/10 flex items-center justify-center shrink-0 mt-0.5">
                        <span className="text-secondary text-[10px] font-bold">{idx + 1}</span>
                      </div>
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-widest text-secondary/70 mb-1 block">{ins.type}</span>
                        <p className="text-sm text-on-surface leading-relaxed">{ins.text}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-400 italic">No additional correlations found.</p>
                )}
             </div>
          </div>

          {/* Anomalies Alert Area */}
          {insights.anomalies && insights.anomalies.length > 0 && (
             <div className="bg-error-container/20 rounded-2xl border border-error/20 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-error/10 bg-error/5 flex items-center gap-2">
                    <span className="material-symbols-outlined text-[18px] text-error">warning</span>
                    <span className="text-xs font-bold text-error uppercase tracking-wider">Anomalies Detected</span>
                </div>
                <div className="p-5 flex flex-col gap-3">
                   {insights.anomalies.map((ano, idx) => (
                     <div key={idx} className="bg-white/80 p-3 rounded-lg border border-error/10">
                        <div className="flex justify-between items-center mb-1">
                          <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full ${
                            ano.severity === 'high' ? 'bg-error text-white' : 
                            ano.severity === 'medium' ? 'bg-orange-500 text-white' : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {ano.severity}
                          </span>
                        </div>
                        <p className="text-sm text-slate-800">{ano.text}</p>
                     </div>
                   ))}
                </div>
             </div>
          )}

        </div>
      </div>
    </div>
  );
};
