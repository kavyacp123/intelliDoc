import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '../ui';

interface Dataset {
  dataset_id: string;
  file_name: string;
}

interface SidebarProps {
  datasets: Dataset[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onUpload: (file: File) => Promise<void>;
  onDelete?: (id: string) => void;
  isUploading: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  datasets, 
  activeId, 
  onSelect, 
  onUpload,
  onDelete,
  isUploading
}) => {
  const location = useLocation();
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <aside className="hidden md:flex flex-col p-6 gap-y-4 h-full w-72 border-r border-slate-200/15 bg-slate-50 transition-all duration-200 ease-in-out">
      <div className="mb-8 flex flex-col">
        <h2 className="text-sm font-semibold tracking-tight uppercase text-on-surface-variant mb-4 px-2">Datasets</h2>
        <input 
          type="file" 
          ref={fileInputRef}
          className="hidden" 
          accept=".csv,.xlsx,.xls,.json" 
          onChange={handleFileChange}
        />
        <Button 
          onClick={() => fileInputRef.current?.click()}
          isLoading={isUploading}
          className="w-full"
        >
          <span className="material-symbols-outlined text-sm">add</span>
          <span>{isUploading ? 'Uploading...' : 'Upload Dataset'}</span>
        </Button>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto">
        <div>
          <h3 className="text-[10px] font-bold tracking-[0.1em] uppercase text-on-surface-variant mb-3 px-3">Active Sources</h3>
          <div className="space-y-1">
            {datasets.length > 0 ? (
              datasets.map((d) => (
                <button
                  key={d.dataset_id}
                  onClick={() => onSelect(d.dataset_id)}
                  className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all group ${
                    d.dataset_id === activeId 
                      ? 'bg-white shadow-sm border-l-2 border-secondary text-slate-900 font-semibold' 
                      : 'hover:bg-slate-200/50 text-on-surface-variant/70 border-l-2 border-transparent'
                  }`}
                >
                  <span className={`material-symbols-outlined text-lg ${d.dataset_id === activeId ? 'text-secondary' : ''}`}>
                    table_chart
                  </span>
                  <div className="flex-1 truncate text-xs text-left">{d.file_name}</div>
                  {onDelete && (
                    <div 
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-300 text-red-500 rounded transition-opacity"
                      onClick={(e) => { e.stopPropagation(); onDelete(d.dataset_id); }}
                    >
                      <span className="material-symbols-outlined text-[16px]">delete</span>
                    </div>
                  )}
                </button>
              ))
            ) : (
              <div className="px-3 text-xs text-on-surface-variant italic">No datasets uploaded yet...</div>
            )}
          </div>
        </div>
        <div>
          <h3 className="text-[10px] font-bold tracking-[0.1em] uppercase text-on-surface-variant mb-3 px-3">Advanced Tools</h3>
          <div className="space-y-1">
            <Link
              to="/profit-engine"
              className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
                location.pathname === '/profit-engine'
                  ? 'bg-white shadow-sm border-l-2 border-primary text-slate-900 font-semibold'
                  : 'hover:bg-slate-200/50 text-on-surface-variant/70 border-l-2 border-transparent'
              }`}
            >
              <span className={`material-symbols-outlined text-lg ${location.pathname === '/profit-engine' ? 'text-primary' : ''}`}>
                monitoring
              </span>
              <div className="flex-1 truncate text-xs text-left">Profit Engine</div>
            </Link>
          </div>
        </div>
      </nav>
    </aside>
  );
};
