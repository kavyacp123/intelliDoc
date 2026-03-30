import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip
} from 'recharts';

interface ChartSeries {
  name: string;
  data: number[];
}

interface GenericChartProps {
  type: string;
  title: string;
  x: string[];
  series: ChartSeries[];
}

export const GenericChart: React.FC<GenericChartProps> = ({ type, title, x, series }) => {
  // Format data for Recharts: [{ name: 'Jan', value: 100 }, ...]
  const chartData = x.map((label, index) => {
    const entry: any = { name: label };
    series.forEach(s => {
      entry[s.name] = s.data[index] || 0;
    });
    return entry;
  });

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-panel p-3 rounded-lg border border-outline-variant text-xs shadow-xl">
          <p className="font-bold mb-1 text-on-surface">{label}</p>
          {payload.map((p: any, i: number) => (
            <p key={i} style={{ color: p.color }} className="flex justify-between gap-4">
              <span>{p.name}:</span>
              <span className="font-mono font-bold">${p.value.toLocaleString()}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  const renderChart = () => {
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

    if (type === 'bar') {
      return (
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.3} />
          <XAxis 
            dataKey="name" 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 10, fill: '#64748b' }} 
            dy={10}
          />
          <YAxis 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 10, fill: '#64748b' }} 
            tickFormatter={(value) => `$${value >= 1000 ? (value / 1000).toFixed(0) + 'k' : value}`}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.05)' }} />
          {series.map((s, i) => (
            <Bar 
              key={s.name} 
              dataKey={s.name} 
              fill={colors[i % colors.length]} 
              radius={[4, 4, 0, 0]} 
              barSize={32}
            />
          ))}
        </BarChart>
      );
    }

    return (
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.3} />
        <XAxis 
          dataKey="name" 
          axisLine={false} 
          tickLine={false} 
          tick={{ fontSize: 10, fill: '#64748b' }} 
          dy={10}
        />
        <YAxis 
          axisLine={false} 
          tickLine={false} 
          tick={{ fontSize: 10, fill: '#64748b' }}
          tickFormatter={(value) => `$${value >= 1000 ? (value / 1000).toFixed(0) + 'k' : value}`}
        />
        <Tooltip content={<CustomTooltip />} />
        {series.map((s, i) => (
          <Line 
            key={s.name} 
            type="monotone" 
            dataKey={s.name} 
            stroke={colors[i % colors.length]} 
            strokeWidth={3}
            dot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />
        ))}
      </LineChart>
    );
  };

  return (
    <div className="glass-panel p-6 rounded-2xl flex flex-col gap-4 border border-outline-variant h-[350px]">
      <h3 className="text-sm font-bold tracking-tight text-on-surface uppercase opacity-60">
        {title}
      </h3>
      <div className="flex-1 w-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );
};
