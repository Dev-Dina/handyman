import { useEffect, useRef, useState } from 'react';
import {
  ChatMessage,
  WidgetConfig,
  fetchWidgetConfig,
  sendChatMessage,
} from './api';
import {
  API_BASE_PARAM,
  DEFAULT_API_BASE,
  PANEL_HEIGHT_PX,
  PANEL_WIDTH_PX,
  RESIZE_MESSAGE_TYPE,
  WIDGET_ID_PARAM,
} from './config';
import './styles.css';

function getUrlParams(): { widgetId: string | null; apiBase: string } {
  const params = new URLSearchParams(window.location.search);
  return {
    widgetId: params.get(WIDGET_ID_PARAM),
    apiBase: params.get(API_BASE_PARAM) ?? DEFAULT_API_BASE,
  };
}

export default function App() {
  const { widgetId, apiBase } = getUrlParams();

  const [config, setConfig] = useState<WidgetConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!widgetId) {
      setConfigError('Missing widget_id parameter.');
      return;
    }
    fetchWidgetConfig(widgetId, apiBase)
      .then((cfg) => {
        setConfig(cfg);
        if (cfg.greeting) {
          setMessages([{ role: 'assistant', content: cfg.greeting }]);
        }
      })
      .catch(() => setConfigError('Could not load widget configuration.'));
  }, [widgetId, apiBase]);

  useEffect(() => {
    window.parent.postMessage(
      {
        type: RESIZE_MESSAGE_TYPE,
        expanded,
        width: PANEL_WIDTH_PX,
        height: PANEL_HEIGHT_PX,
      },
      '*',
    );
  }, [expanded]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    try {
      const resp = await sendChatMessage(
        text,
        conversationId,
        config?.enabled_tools ?? [],
        apiBase,
      );
      setConversationId(resp.conversation_id);
      setMessages((prev) => [...prev, { role: 'assistant', content: resp.answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const primaryColor = config?.theme?.color ?? '#4f46e5';

  if (!expanded) {
    return (
      <button
        className="bubble"
        style={{ background: primaryColor }}
        onClick={() => setExpanded(true)}
        aria-label="Open chat"
      >
        💬
      </button>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header" style={{ background: primaryColor }}>
        <span>Chat</span>
        <button
          className="close-btn"
          onClick={() => setExpanded(false)}
          aria-label="Close chat"
        >
          ×
        </button>
      </div>
      <div className="panel-messages">
        {configError && <div className="message error">{configError}</div>}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {loading && <div className="message loading">…</div>}
        <div ref={messagesEndRef} />
      </div>
      <div className="panel-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void handleSend()}
          placeholder="Type a message…"
          disabled={loading}
          aria-label="Chat input"
        />
        <button
          onClick={() => void handleSend()}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
