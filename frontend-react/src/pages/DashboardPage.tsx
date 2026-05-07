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
  clarificationQuestion?: string;
  confidenceScore?: number;
  clarificationTerms?: string[];
  interactionType?: string;
  interactionPayload?: any;
  sessionId?: string;
  interpretation?: string;
  correctionPrompt?: string;
  assumedDefaults?: string[];
}

interface ClarificationFeedback {
  originalQuery: string;
  selectedOption: string;
  ambiguousTerms: string[];
  sessionId?: string;
  answerKey?: string;
  answerValue?: string;
  correctedQuery?: string;
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
  const [openCorrectionId, setOpenCorrectionId] = useState<string | null>(null);
  const [correctionDrafts, setCorrectionDrafts] = useState<Record<string, string>>({});
  const chatHistoryRef = useRef<HTMLDivElement>(null);

  const activeMessages = activeDatasetId ? chatHistories[activeDatasetId] || [] : [];

  const getCurrentSessionId = () => {
    const messages = activeDatasetId ? chatHistories[activeDatasetId] || [] : [];
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].sessionId) return messages[i].sessionId;
    }
    return undefined;
  };

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

  const handleSend = async (
    overrideQuery?: string,
    clarificationFeedback?: ClarificationFeedback
  ) => {
    const text = clarificationFeedback?.selectedOption || overrideQuery || query.trim();
    if (!text || !activeDatasetId) return;

    if (!overrideQuery) setQuery('');
    
    // 1. Add User Message
    addMessage(activeDatasetId, { id: Date.now().toString(), type: 'user', content: text });
    setIsThinking(true);

    try {
      // 2. Execute Query
      await executeQuery(activeDatasetId, text, clarificationFeedback);
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

  const updateCorrectionDraft = (messageId: string, value: string) => {
    setCorrectionDrafts(prev => ({
      ...prev,
      [messageId]: value
    }));
  };

  const submitCorrection = (message: Message) => {
    const draft = (correctionDrafts[message.id] || '').trim();
    const originalQuery = message.originalQuery || '';
    if (!draft || !activeDatasetId) return;

    setOpenCorrectionId(null);
    updateCorrectionDraft(message.id, '');
    handleSend(draft, {
      originalQuery,
      selectedOption: draft,
      ambiguousTerms: message.clarificationTerms?.length ? message.clarificationTerms : ['correction'],
      sessionId: message.sessionId || getCurrentSessionId(),
      answerKey: 'correction',
      answerValue: draft,
      correctedQuery: originalQuery
        ? `${originalQuery}. Correction from user: ${draft}`
        : draft
    });
  };

  const executeQuery = async (
    datasetId: string,
    text: string,
    clarificationFeedback?: ClarificationFeedback
  ) => {
    try {
      const res = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: clarificationFeedback?.correctedQuery || clarificationFeedback?.originalQuery || text,
          dataset_id: datasetId,
          session_id: clarificationFeedback?.sessionId || getCurrentSessionId(),
          answer_key: clarificationFeedback?.answerKey,
          answer_value: clarificationFeedback?.answerValue,
          clarification_feedback: clarificationFeedback ? {
            original_query: clarificationFeedback.originalQuery,
            selected_option: clarificationFeedback.selectedOption,
            ambiguous_terms: clarificationFeedback.ambiguousTerms,
            session_id: clarificationFeedback.sessionId,
            answer_key: clarificationFeedback.answerKey,
            answer_value: clarificationFeedback.answerValue
          } : undefined
        })
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

          const assistantMessage = {
            id: 'ans-' + Date.now(),
            type: 'assistant' as const,
            data: data.data,
            sql: data.sql,
            rowCount: data.row_count,
            insights: data.insights,
            originalQuery: clarificationFeedback?.originalQuery || text,
            confidenceScore: data.confidence_score,
            sessionId: data.session_id,
            interpretation: data.interpretation,
            correctionPrompt: data.correction_prompt,
            assumedDefaults: data.assumed_defaults || []
          };

          if (Array.isArray(data.data) && (data.data.length > 0 || data.interpretation || data.correction_prompt)) {
            addMessage(datasetId, assistantMessage);
          }

          if (data.needs_clarification) {
            addMessage(datasetId, {
              id: 'clarify-' + Date.now(),
              type: 'suggestions',
            suggestions: data.clarification_options || [],
            originalQuery: text,
            content: data.clarification_question || 'I need a bit more detail before I run that.',
            clarificationQuestion: data.clarification_question,
            confidenceScore: data.confidence_score,
            clarificationTerms: data.clarification_terms || [],
              interactionType: data.interaction_type,
              interactionPayload: data.interaction_payload,
              sessionId: data.session_id
            });
          } else if (!Array.isArray(data.data) || data.data.length === 0) {
            addMessage(datasetId, assistantMessage);
          }
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
                    <div>
                      {(msg.interactionType === 'clarification_chat' || msg.interactionType === 'multi_slot_clarification') && msg.interactionPayload ? (
                        <div className="flex gap-6 max-w-4xl mb-4 animate-in slide-in-from-left-4 fade-in">
                          <div className="w-8 h-8 mt-1 shrink-0">
                            <span className="material-symbols-outlined text-secondary font-fill" style={{ fontVariationSettings: "'FILL' 1" }}>
                              forum
                            </span>
                          </div>
                          <div className="bg-amber-50 text-amber-900 px-5 py-4 rounded-2xl border border-amber-100 shadow-sm w-full">
                            <p className="text-sm font-medium mb-3">{msg.interactionPayload.message || msg.clarificationQuestion}</p>
                            <div className="space-y-3">
                              {(msg.interactionPayload.questions || []).map((q: any, idx: number) => (
                                <div key={idx}>
                                  <p className="text-xs font-semibold mb-2 opacity-80">{q.question}</p>
                                  {msg.interactionPayload.answers?.[q.key] && (
                                    <p className="text-[11px] mb-2 text-emerald-700">
                                      Answered: {msg.interactionPayload.answers[q.key]}
                                    </p>
                                  )}
                                  <div className="flex flex-wrap gap-2">
                                    {(q.options || []).filter(Boolean).map((opt: string, optIdx: number) => (
                                      <button
                                        key={optIdx}
                                        onClick={() => handleSend(
                                          opt,
                                          msg.clarificationTerms && msg.clarificationTerms.length > 0
                                            ? {
                                                originalQuery: msg.originalQuery || '',
                                                selectedOption: opt,
                                                ambiguousTerms: msg.clarificationTerms,
                                                sessionId: msg.sessionId,
                                                answerKey: q.key,
                                                answerValue: opt
                                              }
                                            : undefined
                                        )}
                                        className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-white border border-secondary/20 text-secondary rounded-xl text-xs font-semibold shadow-sm hover:bg-secondary hover:text-white transition-all duration-200 active:scale-95"
                                        disabled={Boolean(msg.interactionPayload.answers?.[q.key])}
                                      >
                                        {opt}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                            {typeof msg.confidenceScore === 'number' && (
                              <p className="text-xs mt-3 opacity-70">Confidence: {Math.round(msg.confidenceScore * 100)}%</p>
                            )}
                          </div>
                        </div>
                      ) : msg.clarificationQuestion && (
                        <div className="flex gap-6 max-w-4xl mb-4 animate-in slide-in-from-left-4 fade-in">
                          <div className="w-8 h-8 mt-1 shrink-0">
                            <span className="material-symbols-outlined text-secondary font-fill" style={{ fontVariationSettings: "'FILL' 1" }}>
                              help
                            </span>
                          </div>
                          <div className="bg-amber-50 text-amber-900 px-5 py-4 rounded-2xl border border-amber-100 shadow-sm">
                            <p className="text-sm font-medium">{msg.clarificationQuestion}</p>
                            {typeof msg.confidenceScore === 'number' && (
                              <p className="text-xs mt-1 opacity-70">Confidence: {Math.round(msg.confidenceScore * 100)}%</p>
                            )}
                          </div>
                        </div>
                      )}
                      {msg.interactionType !== 'clarification_chat' && (
                        <SuggestionBox 
                          suggestions={msg.suggestions || []} 
                          originalQuery={msg.originalQuery || ''} 
                          message={msg.interactionPayload?.message || msg.clarificationQuestion || undefined}
                          onPick={(q) => handleSend(
                            q,
                            msg.clarificationTerms && msg.clarificationTerms.length > 0
                              ? {
                                  originalQuery: msg.originalQuery || '',
                                  selectedOption: q,
                                  ambiguousTerms: msg.clarificationTerms,
                                  sessionId: msg.sessionId,
                                  answerValue: q
                                }
                              : undefined
                          )}
                        />
                      )}
                    </div>
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
                            {(msg.interpretation || msg.correctionPrompt || (msg.assumedDefaults && msg.assumedDefaults.length > 0)) && (
                              <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm text-slate-700">
                                {msg.interpretation && (
                                  <p className="mb-2"><span className="font-semibold text-slate-900">Interpretation:</span> {msg.interpretation}</p>
                                )}
                                {msg.assumedDefaults && msg.assumedDefaults.length > 0 && (
                                  <div className="mb-2">
                                    <p className="font-semibold text-slate-900">Assumptions used:</p>
                                    <ul className="mt-1 space-y-1">
                                      {msg.assumedDefaults.map((assumption, idx) => (
                                        <li key={idx} className="text-xs text-slate-600">- {assumption}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {msg.correctionPrompt && (
                                  <div className="mt-3 border-t border-slate-200 pt-3">
                                    {openCorrectionId === msg.id ? (
                                      <div className="rounded-xl border border-secondary/20 bg-white p-3 shadow-sm">
                                        <label className="mb-2 block text-xs font-semibold text-slate-800">
                                          What should change?
                                        </label>
                                        <textarea
                                          value={correctionDrafts[msg.id] || ''}
                                          onChange={(e) => updateCorrectionDraft(msg.id, e.target.value)}
                                          onKeyDown={(e) => {
                                            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                                              e.preventDefault();
                                              submitCorrection(msg);
                                            }
                                          }}
                                          className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-secondary focus:bg-white focus:ring-2 focus:ring-secondary/10"
                                          placeholder="Example: use gross_total instead of net_profit, group by customer, and only show last month."
                                          autoFocus
                                        />
                                        <div className="mt-3 flex flex-wrap items-center gap-2">
                                          <Button
                                            variant="secondary"
                                            className="h-8 px-3 text-xs font-semibold"
                                            onClick={() => submitCorrection(msg)}
                                            disabled={!correctionDrafts[msg.id]?.trim() || isThinking}
                                          >
                                            <span className="material-symbols-outlined text-[15px]">refresh</span>
                                            Update answer
                                          </Button>
                                          <Button
                                            variant="ghost"
                                            className="h-8 px-3 text-xs"
                                            onClick={() => {
                                              setOpenCorrectionId(null);
                                              updateCorrectionDraft(msg.id, '');
                                            }}
                                          >
                                            Cancel
                                          </Button>
                                          <span className="ml-auto text-[10px] text-slate-400">Cmd/Ctrl + Enter</span>
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-xs text-slate-500">{msg.correctionPrompt}</span>
                                        <button
                                          type="button"
                                          onClick={() => setOpenCorrectionId(msg.id)}
                                          className="inline-flex h-7 items-center gap-1.5 rounded-full border border-secondary/20 bg-white px-3 text-[11px] font-semibold text-secondary shadow-sm transition hover:border-secondary/40 hover:bg-secondary hover:text-white active:scale-95"
                                        >
                                          <span className="material-symbols-outlined text-[14px]">edit</span>
                                          Not right?
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
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
