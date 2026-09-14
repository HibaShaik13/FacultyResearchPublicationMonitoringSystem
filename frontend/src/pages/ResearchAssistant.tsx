import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import {
  Bot,
  Send,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  FileText,
  TrendingUp,
  Database,
  Trash2,
  User,
  ArrowUpRight,
} from 'lucide-react';

interface Citation {
  id?: string;
  title: string;
  year?: number | null;
  venue?: string | null;
  citations?: number;
  doi?: string | null;
  status?: string;
}

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  citations?: Citation[];
  provenance?: string;
  suggested_actions?: string[];
  timestamp: string;
}

export default function ResearchAssistant() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome-1',
      sender: 'assistant',
      text: "### Welcome to the Vignan Research Intelligence Assistant\n\nI can answer questions regarding your **publications, citation metrics, verification status, h-index, research specializations, and NAAC/NIRF accreditation evidence**.\n\nAll my responses are **100% grounded in verified system data** with provenance tracking.",
      provenance: "VFSTR Research Intelligence Platform",
      suggested_actions: [
        "What are my top cited publications?",
        "What is my current h-index & citation impact?",
        "Show my publications from 2023",
        "Check my verification and integrity status",
        "Show NAAC Criterion 3 verified evidence",
      ],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [inputMsg, setInputMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || inputMsg;
    if (!textToSend.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    if (!queryText) setInputMsg('');
    setIsLoading(true);

    try {
      const res = await api.post('/api/v1/agents/chat', { message: textToSend.trim() });
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        text: res.data.reply,
        citations: res.data.citations || [],
        provenance: res.data.provenance || 'VFSTR Verified Database',
        suggested_actions: res.data.suggested_actions || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        sender: 'assistant',
        text: "I encountered a communication error while querying the research database. Please ensure the backend is running and try again.",
        provenance: "System Gateway",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionClick = (action: string) => {
    if (action.includes("View My Publications") || action.includes("View All Publications")) {
      navigate('/publications');
    } else if (action.includes("Verification Queue") || action.includes("Check Verification Status")) {
      navigate('/verification');
    } else if (action.includes("Research Impact") || action.includes("Impact Dashboard")) {
      navigate('/impact');
    } else if (action.includes("Reports") || action.includes("Accreditation") || action.includes("Export NAAC CSV")) {
      navigate('/reports');
    } else if (action.includes("Research Areas")) {
      navigate('/areas');
    } else {
      handleSend(action);
    }
  };

  const renderFormattedText = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, idx) => {
      // Heading 3
      if (line.startsWith('### ')) {
        return (
          <h3 key={idx} className="text-base sm:text-lg font-bold text-slate-900 mt-2 mb-1.5 flex items-center gap-2">
            {line.replace('### ', '')}
          </h3>
        );
      }
      // Heading 4
      if (line.startsWith('#### ')) {
        return (
          <h4 key={idx} className="text-sm font-bold text-slate-800 mt-2 mb-1">
            {line.replace('#### ', '')}
          </h4>
        );
      }
      // Blockquote
      if (line.startsWith('> ')) {
        return (
          <div key={idx} className="pl-3 border-l-2 border-blue-500 text-slate-700 italic text-xs my-1 bg-blue-50/50 py-1 rounded-r-md">
            {line.replace('> ', '')}
          </div>
        );
      }
      // Unordered list
      if (line.startsWith('- ')) {
        return (
          <li key={idx} className="text-xs sm:text-sm text-slate-700 ml-4 list-disc my-0.5 leading-relaxed">
            {renderInlineMarkdown(line.replace('- ', ''))}
          </li>
        );
      }
      // Numbered list
      if (/^\d+\.\s/.test(line)) {
        return (
          <div key={idx} className="text-xs sm:text-sm text-slate-800 ml-2 font-medium my-1">
            {renderInlineMarkdown(line)}
          </div>
        );
      }
      // Table rows (simple parser)
      if (line.startsWith('|') && line.endsWith('|')) {
        if (line.includes('---')) return null; // divider
        const cells = line.split('|').slice(1, -1);
        return (
          <div key={idx} className="grid grid-cols-3 gap-2 text-xs py-1 border-b border-slate-100 font-medium">
            {cells.map((c, i) => (
              <span key={i} className={i === 0 ? 'text-slate-600' : 'text-slate-900 font-semibold'}>
                {renderInlineMarkdown(c.trim())}
              </span>
            ))}
          </div>
        );
      }
      // Empty line
      if (!line.trim()) {
        return <div key={idx} className="h-1.5" />;
      }
      // Normal paragraph
      return (
        <p key={idx} className="text-xs sm:text-sm text-slate-700 leading-relaxed my-0.5">
          {renderInlineMarkdown(line)}
        </p>
      );
    });
  };

  const renderInlineMarkdown = (text: string) => {
    // Replace **bold**
    const parts = text.split(/(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={i} className="bg-slate-100 text-blue-700 px-1 py-0.5 rounded text-[11px] font-mono">{part.slice(1, -1)}</code>;
      }
      if (part.startsWith('[') && part.includes('](') && part.endsWith(')')) {
        const title = part.slice(1, part.indexOf(']('));
        const url = part.slice(part.indexOf('](') + 2, -1);
        return (
          <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 underline font-medium inline-flex items-center gap-0.5">
            {title} <ExternalLink size={10} />
          </a>
        );
      }
      return part;
    });
  };

  return (
    <div className="max-w-6xl mx-auto space-y-4 pb-12 font-sans">
      {/* Header Bar */}
      <div className="bg-white/90 backdrop-blur-md rounded-2xl p-5 border border-slate-200/80 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-blue-700 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-600/20">
            <Bot size={24} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-slate-900">Research Intelligence Assistant</h1>
              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 font-bold text-[10px] rounded-full uppercase tracking-wider">
                AI Assistant
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Natural language answers strictly grounded in verified VFSTR research records and citation engines.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <button
            onClick={() =>
              setMessages([
                {
                  id: 'welcome-reset',
                  sender: 'assistant',
                  text: "Conversation reset. How can I assist you with your research data today?",
                  provenance: "VFSTR Database",
                  suggested_actions: [
                    "What are my top cited publications?",
                    "What is my current h-index?",
                    "Show my publications from 2023",
                    "Check verification status",
                  ],
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                },
              ])
            }
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-xl text-xs font-medium transition-colors"
          >
            <Trash2 size={13} />
            <span>Clear Chat</span>
          </button>
        </div>
      </div>

      {/* Main Chat Conversation Container */}
      <div className="bg-white/80 backdrop-blur-xl rounded-3xl border border-slate-200/80 shadow-lg flex flex-col h-[72vh] overflow-hidden">
        {/* Messages Stream */}
        <div className="flex-1 p-5 sm:p-6 overflow-y-auto space-y-6">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex gap-3.5 max-w-3xl ${
                m.sender === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
              }`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 text-white shadow-sm ${
                  m.sender === 'user'
                    ? 'bg-gradient-to-tr from-blue-600 to-sky-600'
                    : 'bg-gradient-to-tr from-indigo-700 to-blue-800'
                }`}
              >
                {m.sender === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>

              {/* Message Content Bubble */}
              <div className="space-y-2.5 max-w-[85%]">
                <div
                  className={`p-4 sm:p-5 rounded-2xl shadow-sm text-sm ${
                    m.sender === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-slate-50 border border-slate-200/90 text-slate-800 rounded-tl-none'
                  }`}
                >
                  {m.sender === 'user' ? (
                    <p className="font-medium leading-relaxed">{m.text}</p>
                  ) : (
                    <div className="space-y-1">{renderFormattedText(m.text)}</div>
                  )}

                  {/* Direct Publication Citation Cards */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-3.5 pt-3 border-t border-slate-200/80 space-y-2">
                      <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                        <FileText size={12} className="text-blue-600" /> Linked Verified Publications ({m.citations.length})
                      </p>
                      <div className="grid grid-cols-1 gap-2">
                        {m.citations.map((c, i) => (
                          <div
                            key={i}
                            className="bg-white p-3 rounded-xl border border-slate-200/90 shadow-sm flex flex-col justify-between gap-1.5 hover:border-blue-300 transition-all"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="text-xs font-bold text-slate-900 line-clamp-2">
                                {c.title}
                              </span>
                              {c.status && (
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[9px] font-extrabold flex-shrink-0 ${
                                    c.status === 'VERIFIED'
                                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                                  }`}
                                >
                                  {c.status}
                                </span>
                              )}
                            </div>

                            <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                              {c.year && <span>Year: <strong className="text-slate-700">{c.year}</strong></span>}
                              {c.venue && <span>Venue: <em className="text-slate-700">{c.venue}</em></span>}
                              {c.citations !== undefined && (
                                <span className="flex items-center gap-1 font-bold text-blue-700">
                                  <TrendingUp size={11} /> {c.citations} Citations
                                </span>
                              )}
                              {c.doi && (
                                <a
                                  href={`https://doi.org/${c.doi}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center gap-0.5 ml-auto"
                                >
                                  DOI <ArrowUpRight size={11} />
                                </a>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Provenance Badge */}
                  {m.provenance && m.sender === 'assistant' && (
                    <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-400">
                      <span className="flex items-center gap-1 font-medium text-slate-500">
                        <Database size={11} className="text-emerald-600" /> {m.provenance}
                      </span>
                      <span>{m.timestamp}</span>
                    </div>
                  )}
                </div>

                {/* Suggested Action Chips */}
                {m.suggested_actions && m.suggested_actions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {m.suggested_actions.map((act, i) => (
                      <button
                        key={i}
                        onClick={() => handleActionClick(act)}
                        className="px-2.5 py-1 bg-white hover:bg-blue-50 border border-slate-200/90 text-blue-700 hover:border-blue-300 rounded-full text-[11px] font-semibold shadow-2xs flex items-center gap-1 transition-all"
                      >
                        <Sparkles size={11} className="text-blue-500" />
                        <span>{act}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Typing Loading Indicator */}
          {isLoading && (
            <div className="flex gap-3.5 max-w-xl mr-auto">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-700 to-blue-800 flex items-center justify-center flex-shrink-0 text-white shadow-sm animate-pulse">
                <Bot size={16} />
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 shadow-sm space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce" />
                  <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.2s]" />
                  <div className="w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.4s]" />
                  <span className="text-xs font-semibold text-slate-500 ml-1">
                    Querying verified research database & citation graphs...
                  </span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Form Bar */}
        <div className="p-4 bg-slate-50/90 border-t border-slate-200/80">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex items-center"
          >
            <input
              type="text"
              value={inputMsg}
              onChange={(e) => setInputMsg(e.target.value)}
              placeholder="Ask about your publications, h-index, citations, verification queue, or NAAC accreditation..."
              disabled={isLoading}
              className="w-full bg-white border border-slate-200/90 rounded-2xl pl-5 pr-14 py-3.5 text-xs sm:text-sm text-slate-900 font-medium placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 shadow-inner disabled:opacity-60 transition-all"
            />
            <button
              type="submit"
              disabled={!inputMsg.trim() || isLoading}
              className="absolute right-2.5 p-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-md shadow-blue-600/25 disabled:opacity-40 disabled:hover:bg-blue-600 transition-all cursor-pointer"
            >
              <Send size={16} />
            </button>
          </form>
          <div className="flex items-center justify-between mt-2 px-1 text-[11px] text-slate-400">
            <span>Press Enter to send • Verified Data Grounded</span>
            <span className="flex items-center gap-1 font-medium text-slate-500">
              <ShieldCheck size={12} className="text-emerald-600" /> Data Isolation & RBAC Active
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
