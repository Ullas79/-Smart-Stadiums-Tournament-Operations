import { useState, useRef, useEffect, useCallback, memo } from "react";
import type { Message, Role, ToolEvent } from "../types";
import { sendChat } from "../api";
import "./ChatPanel.css";

interface Props {
  role: Role;
  language: string;
}

interface DisplayMessage extends Message {
  id?: string;
  toolEvents?: ToolEvent[];
  pending?: boolean;
}

const SUGGESTIONS: Record<Role, string[]> = {
  fan: [
    "How do I get to my seat in Lower North?",
    "What's the bag policy?",
    "Which restroom is least crowded?",
  ],
  volunteer: [
    "Where are the active incidents?",
    "How's the crowd at the gates?",
    "What's the schedule?",
  ],
  organizer: [
    "Give me operational recommendations.",
    "What's the crowd status across all zones?",
    "Any high-severity incidents?",
  ],
  staff: [
    "Set Gate 2 to restricted.",
    "Dispatch Staff-John to active incidents.",
    "Mitigate bottleneck in Lower North.",
  ],
};

export const ChatPanel = memo(function ChatPanel({ role, language }: Props) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [liveAnnouncement, setLiveAnnouncement] = useState("");

  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef(messages);
  const busyRef = useRef(busy);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Synchronize state values into refs for callback stabilization and avoiding stale closures
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  // Handle scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current;
    if (el && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  // Handle dynamic updates announcement for WCAG 4.1.3 compliance
  useEffect(() => {
    if (messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role === "user") {
      setLiveAnnouncement(`Sent: ${lastMsg.content}`);
    } else if (lastMsg.role === "assistant") {
      if (lastMsg.pending) {
        setLiveAnnouncement("Assistant is typing...");
      } else {
        const toolCalls = lastMsg.toolEvents?.length || 0;
        const toolSuffix = toolCalls > 0 ? ` (${toolCalls} tool calls run)` : "";
        setLiveAnnouncement(`Assistant: ${lastMsg.content}${toolSuffix}`);
      }
    }
  }, [messages]);

  // Cancel any pending request when role or language changes, or component unmounts
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [role, language]);

  const submit = useCallback(async (text: string): Promise<void> => {
    const trimmed = text.trim();
    if (!trimmed || busyRef.current) return;

    // Synchronously set busy status to prevent concurrent double-submissions
    busyRef.current = true;
    setBusy(true);

    // Cancel any existing pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const currentMessages = messagesRef.current;
    const history: Message[] = currentMessages.map(({ role: r, content }) => ({ role: r, content }));
    const userMsg: DisplayMessage = { role: "user", content: trimmed };
    
    // Assign a unique ID to the pending assistant reply to map/update it without scope errors or slicing bugs
    const pendingId = `pending-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const pendingMsg: DisplayMessage = { id: pendingId, role: "assistant", content: "", pending: true };

    setMessages((m) => [...m, userMsg, pendingMsg]);
    setInput("");

    try {
      const res = await sendChat(trimmed, role, history, language, controller.signal);
      setMessages((m) =>
        m.map((msg) =>
          msg.id === pendingId
            ? { role: "assistant", content: res.reply, toolEvents: res.tool_events }
            : msg
        )
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setMessages((m) => m.filter((msg) => msg.id !== pendingId));
        return;
      }
      setMessages((m) =>
        m.map((msg) =>
          msg.id === pendingId
            ? { role: "assistant", content: `⚠️ Error: ${(e as Error).message}` }
            : msg
        )
      );
    } finally {
      if (abortControllerRef.current === controller) {
        busyRef.current = false;
        setBusy(false);
        abortControllerRef.current = null;
      }
    }
  }, [role, language]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    submit(input).catch((err) => {
      console.error("Failed to submit chat message:", err);
    });
  }, [submit, input]);

  return (
    <section className="chat-panel" aria-label="Assistant chat">
      {/* Dynamic Screen Reader Announcer */}
      <div className="sr-only" aria-live="polite" role="status" aria-atomic="true">
        {liveAnnouncement}
      </div>

      <div
        className="chat-messages"
        ref={scrollRef}
        tabIndex={0}
        aria-label="Chat messages history"
      >
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask the Smart Stadiums Assistant about navigation, crowds, schedule, or incidents.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role} ${m.pending ? "pending" : ""}`}>
            <div className="chat-msg-role">{m.role === "user" ? "You" : "Assistant"}</div>
            <div className="chat-msg-content">
              {m.pending ? (
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              ) : (
                m.content
              )}
              {m.toolEvents && m.toolEvents.length > 0 && (
                <details className="chat-tools">
                  <summary>{m.toolEvents.length} tool call(s)</summary>
                  <ul>
                    {m.toolEvents.map((t, j) => (
                      <li key={j} className={t.error ? "tool-error" : ""}>
                        <code>{t.name}</code>{" "}
                        <span className="tool-status">
                          {t.error ? (
                            <span aria-label="error">⚠️ error</span>
                          ) : (
                            <span aria-label="completed successfully">✓</span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="chat-suggestions" role="group" aria-label="Suggested prompts">
        {SUGGESTIONS[role].map((s) => (
          <button
            key={s}
            className="suggestion"
            onClick={() => {
              submit(s).catch((err) => {
                console.error("Failed to submit suggestion:", err);
              });
            }}
            disabled={busy}
          >
            {s}
          </button>
        ))}
      </div>

      <form
        className="chat-input"
        onSubmit={handleSubmit}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Ask as ${role}…`}
          disabled={busy}
          aria-label="Message text"
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  );
});
