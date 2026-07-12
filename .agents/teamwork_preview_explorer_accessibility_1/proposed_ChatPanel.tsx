import { useState, useRef, useEffect, useCallback, memo } from "react";
import type { Message, Role, ToolEvent } from "../types";
import { sendChat } from "../api";
import "./ChatPanel.css";

interface Props {
  role: Role;
  language: string;
}

interface DisplayMessage extends Message {
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

  const submit = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    const history: Message[] = messages.map(({ role: r, content }) => ({ role: r, content }));
    const userMsg: DisplayMessage = { role: "user", content: trimmed };
    const pendingMsg: DisplayMessage = { role: "assistant", content: "", pending: true };
    setMessages((m) => [...m, userMsg, pendingMsg]);
    setInput("");
    setBusy(true);
    try {
      const res = await sendChat(trimmed, role, history, language);
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: "assistant", content: res.reply, toolEvents: res.tool_events },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: "assistant", content: `⚠️ Error: ${(e as Error).message}` },
      ]);
    } finally {
      setBusy(false);
    }
  }, [messages, busy, role, language]);

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
                <span aria-label="Assistant is typing...">…</span>
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
