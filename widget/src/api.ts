import { DEFAULT_API_BASE } from './config';

export interface WidgetConfig {
  public_widget_id: string;
  theme: Record<string, string>;
  greeting: string | null;
  enabled_tools: string[];
  is_active: boolean;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
  tool_calls: unknown[];
  trace_id: string | null;
}

export async function fetchWidgetConfig(
  widgetId: string,
  apiBase: string = DEFAULT_API_BASE,
): Promise<WidgetConfig> {
  const res = await fetch(`${apiBase}/api/v1/widgets/${encodeURIComponent(widgetId)}`);
  if (!res.ok) {
    throw new Error(`Widget config fetch failed: ${res.status}`);
  }
  return res.json() as Promise<WidgetConfig>;
}

export async function sendChatMessage(
  message: string,
  conversationId: string | null,
  enabledTools: string[],
  apiBase: string = DEFAULT_API_BASE,
): Promise<ChatResponse> {
  const body: Record<string, unknown> = { message };
  if (conversationId) body.conversation_id = conversationId;
  if (enabledTools.length > 0) body.enabled_tools = enabledTools;

  const res = await fetch(`${apiBase}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }
  return res.json() as Promise<ChatResponse>;
}
