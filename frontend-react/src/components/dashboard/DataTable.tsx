import React from 'react';

interface DataTableProps {
  data: any[];
  rowCount: number;
}

export const DataTable: React.FC<DataTableProps> = ({ data, rowCount }) => {
  if (!data || data.length === 0) {
    return (
      <div className="mt-4 p-4 border border-outline-variant/10 rounded-xl bg-slate-50 text-center text-sm text-slate-500 italic">
        No rows returned.
      </div>
    );
  }

  const columns = Object.keys(data[0]);

  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/10 shadow-atmospheric mt-4 overflow-hidden">
      <div className="px-6 py-4 border-b border-outline-variant/10 bg-slate-50/50 flex justify-between items-center">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Results</span>
        <span className="text-[10px] font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
          {rowCount} rows
        </span>
      </div>
      <div className="overflow-x-auto w-full">
        <table className="w-full text-left whitespace-nowrap">
          <thead className="border-b border-outline-variant/15 bg-slate-50">
            <tr className="text-on-surface-variant text-[10px] font-bold uppercase tracking-wider">
              {columns.map((col) => (
                <th key={col} className="py-3 px-4">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody className="text-sm divide-y divide-slate-100">
            {data.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50 transition-colors">
                {columns.map((col) => (
                  <td 
                    key={col} 
                    className={`py-3 px-4 ${typeof row[col] === 'number' ? 'tabular-nums text-right font-medium' : ''}`}
                  >
                    {row[col] !== null ? String(row[col]) : <span className="text-slate-300 italic">null</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
