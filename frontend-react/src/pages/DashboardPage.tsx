import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Sidebar } from '../components/dashboard/Sidebar';
import { DataTable } from '../components/dashboard/DataTable';
import { SuggestionBox } from '../components/dashboard/SuggestionBox';
import { DashboardPanel } from '../components/dashboard/DashboardPanel';
import { Button } from '../components/ui';

interface Message {
  id: string;
  type: 'user' | 'assistant' | 'suggestions';
  content?: string;
  data?: any[];
  sql?: string;
  rowCount?: number;
  error?: string;
  suggestions?: string[];
  originalQuery?: string;
  insights?: any;
}

const DashboardPage: React.FC = () => {
  const { token, logout } = useAuth();
  const [datasets, setDatasets] = useState<any[]>([]);
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);
  const [chatHistories, setChatHistories] = useState<Record<string, Message[]>>({});
  const [query, setQuery] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const chatHistoryRef = useRef<HTMLDivElement>(null);

  const activeMessages = activeDatasetId ? chatHistories[activeDatasetId] || [] : [];

  const authHeaders = {
    'Authorization': `Bearer ${token}`
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    if (chatHistoryRef.current) {
      chatHistoryRef.current.scrollTo({ top: chatHistoryRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [activeMessages, isThinking]);

  useEffect(() => {
    if (activeDatasetId) {
      loadHistory(activeDatasetId);
    }
  }, [activeDatasetId]);

  const loadHistory = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/chat_history/${id}`, {
        headers: authHeaders
      });
      if (res.ok) {
        const data = await res.json();
        setChatHistories(prev => ({
          ...prev,
          [id]: data.messages || []
        }));
      }
    } catch (err) {
      console.error('Failed to load chat history', err);
    }
  };

  const loadDatasets = async () => {
    try {
      const res = await fetch('http://localhost:8000/datasets', { headers: authHeaders });
      const data = await res.json();
      if (res.ok && data) {
        // Simple deduplication
        const unique = [];
        const seen = new Set();
        for (const d of data) {
          if (!seen.has(d.file_name)) {
            seen.add(d.file_name);
            unique.push(d);
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
      } else {
        alert('Upload failed');
      }
    } catch (err) {
      alert('Network error');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    // Only set to false if we're leaving the main container
    if (e.currentTarget === e.target) {
        setIsDragging(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      handleUpload(file);
    }
  };

  const handleDeleteDataset = async (id: string) => {
    if (!window.confirm('Are you sure you want to completely delete this dataset? This cannot be undone.')) return;
    try {
      const res = await fetch(`http://localhost:8000/datasets/${id}`, {
        method: 'DELETE',
        headers: authHeaders
      });
      if (res.ok) {
        setDatasets(prev => {
          const newDatasets = prev.filter(d => d.dataset_id !== id);
          if (activeDatasetId === id) {
            setActiveDatasetId(newDatasets.length > 0 ? newDatasets[0].dataset_id : null);
          }
          return newDatasets;
        });
      } else {
        alert('Failed to delete dataset');
      }
    } catch (err) {
      alert('Network error while deleting dataset');
    }
  };

  const addMessage = (datasetId: string, message: Message) => {
    setChatHistories(prev => ({
      ...prev,
      [datasetId]: [...(prev[datasetId] || []), message]
    }));
    
    // Persist to backend
    fetch('http://localhost:8000/chat_history', {
      method: 'POST',
      headers: { ...authHeaders, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: message.id,
        dataset_id: datasetId,
        message: message
      })
    }).catch(err => console.error('Failed to save message', err));
  };

  const handleSend = async (overrideQuery?: string) => {
    const text = overrideQuery || query.trim();
    if (!text || !activeDatasetId) return;

    if (!overrideQuery) setQuery('');
    
    // 1. Add User Message
    addMessage(activeDatasetId, { id: Date.now().toString(), type: 'user', content: text });
    setIsThinking(true);

    try {
      // 2. Fetch Suggestions (if not an override from a previous suggestion)
      if (!overrideQuery) {
        const suggestRes = await fetch('http://localhost:8000/query/suggest', {
          method: 'POST',
          headers: { ...authHeaders, 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text, dataset_id: activeDatasetId })
        });
        
        if (suggestRes.ok) {
          const suggestData = await suggestRes.json();
          if (suggestData.suggestions && suggestData.suggestions.length > 0) {
            setIsThinking(false);
            addMessage(activeDatasetId, {
              id: 'sug-' + Date.now(),
              type: 'suggestions',
              suggestions: suggestData.suggestions,
              originalQuery: text
            });
            return;
          }
        }
      }

      // 3. Execute Query
      await executeQuery(activeDatasetId, text);
    } catch (err) {
      addMessage(activeDatasetId, { 
        id: 'err-' + Date.now(), 
        type: 'assistant', 
        error: 'Network error communicating with the engine.' 
      });
    } finally {
      setIsThinking(false);
    }
  };

  const executeQuery = async (datasetId: string, text: string) => {
    try {
      const res = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, dataset_id: datasetId })
      });

      const data = await res.json();
      if (res.ok) {
        if (data.status === 'processing') {
            addMessage(datasetId, {
              id: 'ans-' + Date.now(),
              type: 'assistant',
              error: `Query is crunching a large dataset in the background natively. Job ID: ${data.job_id}.`
            });
            return;
        }

        addMessage(datasetId, {
          id: 'ans-' + Date.now(),
          type: 'assistant',
          data: data.data,
          sql: data.sql,
          rowCount: data.row_count,
          insights: data.insights
        });
      } else {
        addMessage(datasetId, {
          id: 'ans-' + Date.now(),
          type: 'assistant',
          error: data.detail || 'Query execution failed.'
        });
      }
    } catch (err) {
      throw err;
    }
  };
  
  const handleDownloadExcel = async (question: string) => {
    if (!activeDatasetId) return;
    
    try {
      const res = await fetch('http://localhost:8000/query/export', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, dataset_id: activeDatasetId })
      });
      
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || 'Export failed');
        return;
      }
      
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `intelliDoc_Export_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      console.error('Export error', err);
      alert('Failed to download Excel file');
    }
  };

  return (
    <div 
      className="flex flex-col h-screen text-on-surface relative"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragging && (
        <div className="absolute inset-0 z-[100] bg-primary/10 backdrop-blur-xs flex items-center justify-center border-4 border-dashed border-primary pointer-events-none">
          <div className="bg-white p-10 rounded-3xl shadow-2xl flex flex-col items-center gap-4 animate-in zoom-in-95 pointer-events-none">
            <span className="material-symbols-outlined text-6xl text-primary block">cloud_upload</span>
            <h2 className="text-2xl font-bold text-slate-900 font-headline">Drop Dataset Here</h2>
            <p className="text-sm text-on-surface-variant font-medium">Uploads CSV, Excel, or JSON instantly.</p>
          </div>
        </div>
      )}

      <header className="h-14 w-full flex items-center justify-between px-6 bg-white border-b border-outline-variant/15 z-50">
        <h1 className="font-headline font-extrabold text-xl tracking-tighter text-slate-900">intelliDoc</h1>
        <div className="flex items-center gap-4">
          <Button variant="secondary" onClick={() => window.location.href='/executive-dashboard'} className="text-xs font-semibold">Executive Dashboard</Button>
          <Button variant="ghost" onClick={logout} className="text-xs font-semibold">Logout</Button>
          <div className="w-8 h-8 rounded-full bg-primary-container border border-outline-variant/30 overflow-hidden">
            <img 
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAguFL3MT8VsqWPEskjtf8vORc90KGC3IQRA5IFQjUuwOCd89e4lZnzFnC2P4MUPpGmMIxmIQZBrhO0IxUKnB3mXvWwZPHsniH9SmgQjrkZuc7TNBG5J5_u1bbFCI4z-ISHhKHz1RYDRN_VzS-SgujwF-ngSexIyfibDkRKm2uPZ9R7sty1hLKKD0TfZKcyD-a5Av1XVOvl-89HpdySxjQRlQHBnDYmKyTF742caejsfbGNq1UOTnbnkvBktNuWKoauNsLV4Kx3d6SK" 
              className="w-full h-full object-cover" 
              alt="Avatar"
            />
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar 
          datasets={datasets} 
          activeId={activeDatasetId} 
          onSelect={setActiveDatasetId}
          onUpload={handleUpload}
          onDelete={handleDeleteDataset}
          isUploading={isUploading}
        />

        <main className="flex-1 flex flex-col relative bg-surface overflow-hidden">
          <header className="flex items-center px-8 h-16 w-full bg-transparent font-headline font-bold text-lg sticky top-0 z-30">
            <span className="text-xl font-extrabold tracking-tighter text-slate-900">AI Analytics</span>
          </header>

          <div ref={chatHistoryRef} className="flex-1 overflow-y-auto px-6 md:px-24 py-6 space-y-12">
            {activeMessages.length === 0 ? (
              <div className="text-center py-20 opacity-50 animate-in fade-in duration-700">
                <span className="material-symbols-outlined text-6xl text-on-surface-variant mb-4 font-fill" style={{ fontVariationSettings: "'FILL' 1" }}>
                  auto_awesome
                </span>
                <h2 className="text-xl font-bold font-headline mb-2">Welcome to intelliDoc</h2>
                <p className="text-sm font-body">Select a dataset and start asking questions.</p>
              </div>
            ) : (
              activeMessages.map((msg) => (
                <div key={msg.id}>
                  {msg.type === 'user' ? (
                    <div className="flex flex-row-reverse gap-6 max-w-4xl ml-auto mb-8 animate-in slide-in-from-right-4 fade-in">
                      <div className="w-8 h-8 rounded-full overflow-hidden shrink-0 mt-1">
                        <img src="https://lh3.googleusercontent.com/a/ACg8ocL... (placeholder)" className="w-full h-full object-cover" />
                      </div>
                      <div className="bg-primary-container text-white px-6 py-4 rounded-2xl max-w-md shadow-sm">
                        <p className="text-sm leading-relaxed">{msg.content}</p>
                      </div>
                    </div>
                  ) : msg.type === 'suggestions' ? (
                    <SuggestionBox 
                      suggestions={msg.suggestions || []} 
                      originalQuery={msg.originalQuery || ''} 
                      onPick={(q) => handleSend(q)}
                    />
                  ) : (
                    <div className="flex gap-6 max-w-4xl mb-8 animate-in slide-in-from-left-4 fade-in">
                      <div className="w-8 h-8 mt-1 shrink-0">
                        <span className="material-symbols-outlined text-secondary font-fill" style={{ fontVariationSettings: "'FILL' 1" }}>
                          auto_awesome
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        {msg.error ? (
                          <div className="bg-red-50 text-red-700 px-6 py-4 rounded-2xl border border-red-100 shadow-sm">
                            <p className="text-sm">{msg.error}</p>
                          </div>
                        ) : (
                          <>
                            {msg.insights ? (
                              <div className="mt-4">
                                <DashboardPanel insights={msg.insights} data={msg.data || []} rowCount={msg.rowCount || 0} />
                              </div>
                            ) : (
                              <>
                                <p className="text-sm text-on-surface mb-4">Here are the results of your query:</p>
                                <DataTable data={msg.data || []} rowCount={msg.rowCount || 0} />
                              </>
                            )}

                            {msg.data && msg.data.length > 0 && (
                              <div className="mt-4 flex flex-wrap gap-2">
                                <Button 
                                  variant="ghost" 
                                  className="text-[10px] h-7 px-3 flex items-center gap-1.5 opacity-60 hover:opacity-100 hover:bg-surface-container-high border border-outline-variant/10 rounded-full"
                                  onClick={() => handleDownloadExcel(msg.originalQuery || msg.content || '')}
                                >
                                  <span className="material-symbols-outlined text-[14px]">download</span>
                                  Download Findings (XLSX)
                                </Button>
                                
                                {msg.sql && (
                                  <details className="inline-block group">
                                    <summary className="text-[10px] h-7 px-3 flex items-center gap-1.5 opacity-60 hover:opacity-100 hover:bg-surface-container-high border border-outline-variant/10 rounded-full cursor-pointer list-none">
                                      <span className="material-symbols-outlined text-[14px]">code</span>
                                      SQL View
                                    </summary>
                                    <div className="absolute left-0 mt-2 p-3 bg-slate-900 rounded-lg border border-slate-800 overflow-x-auto z-40 max-w-full shadow-2xl">
                                      <pre className="text-emerald-400 text-[10px] font-mono leading-tight">{msg.sql}</pre>
                                    </div>
                                  </details>
                                )}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
            
            {isThinking && (
              <div className="flex gap-6 max-w-4xl mb-8">
                <div className="w-8 h-8 mt-1">
                  <span className="material-symbols-outlined text-secondary font-fill" style={{ fontVariationSettings: "'FILL' 1" }}>
                    auto_awesome
                  </span>
                </div>
                <div className="flex items-center gap-2 text-on-surface-variant/50 italic text-sm py-2">
                  <span className="animate-pulse font-medium">Analyzing data...</span>
                </div>
              </div>
            )}
          </div>

          <div className="sticky bottom-0 left-0 right-0 p-6 md:px-24 bg-linear-to-t from-surface to-transparent">
            <div className="max-w-4xl mx-auto">
              <div className="relative flex items-center glass-panel rounded-2xl shadow-atmospheric border border-outline-variant/15 p-2 pr-4 transition-all focus-within:ring-2 ring-secondary/20">
                <textarea 
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  className="flex-1 bg-transparent border-none focus:ring-0 text-on-surface py-3 px-4 resize-none max-h-32 text-sm placeholder:text-on-surface-variant/40" 
                  placeholder="Ask about your financial data..." 
                  rows={1}
                />
                <button 
                  onClick={() => handleSend()}
                  disabled={!query.trim() || !activeDatasetId || isThinking}
                  className="ml-2 p-3 bg-primary text-on-primary rounded-xl flex items-center justify-center hover:opacity-90 active:scale-95 transition-all disabled:opacity-30 disabled:pointer-events-none"
                >
                  <span className="material-symbols-outlined">send</span>
                </button>
              </div>
              <p className="text-[10px] text-center text-on-surface-variant/40 mt-3 tracking-wide">
                AI-powered analysis can make mistakes. Please verify important financial figures.
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default DashboardPage;
