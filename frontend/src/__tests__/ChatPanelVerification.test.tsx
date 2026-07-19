import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, test, expect, beforeEach } from "vitest";
import { ChatPanel } from "../components/ChatPanel";
import { sendChat } from "../api";
import type { ChatResponse } from "../types";

vi.mock("../api");
const mockedSendChat = vi.mocked(sendChat);

beforeEach(() => {
  vi.clearAllMocks();
});

test("prevents concurrent double-submission using busyRef", async () => {
  let resolvePromise: (value: ChatResponse) => void = () => {};
  const chatPromise = new Promise<ChatResponse>((resolve) => {
    resolvePromise = resolve;
  });
  mockedSendChat.mockReturnValue(chatPromise);

  render(<ChatPanel role="fan" language="en" />);

  const input = screen.getByPlaceholderText("Ask as Fan…") as HTMLInputElement;
  const form = screen.getByPlaceholderText("Ask as Fan…").closest("form")!;

  // First submission
  fireEvent.change(input, { target: { value: "Hello first" } });
  fireEvent.submit(form);

  expect(mockedSendChat).toHaveBeenCalledTimes(1);
  expect(mockedSendChat).toHaveBeenLastCalledWith(
    "Hello first",
    "fan",
    [],
    "en",
    expect.any(AbortSignal)
  );

  // Immediate second submission before the first promise resolves
  // Should be blocked by busyRef.current synchronously
  fireEvent.change(input, { target: { value: "Hello second" } });
  fireEvent.submit(form);

  expect(mockedSendChat).toHaveBeenCalledTimes(1);

  // Resolve the first request
  resolvePromise({
    reply: "First reply",
    role: "fan",
    language: "en",
    tool_events: [],
    snapshot_summary: "",
  });

  await waitFor(() => expect(screen.getByText("First reply")).toBeInTheDocument());
});

test("cancels request when role changes", async () => {
  let signalSent: AbortSignal | null = null;
  mockedSendChat.mockImplementation((_text, _role, _history, _lang, signal) => {
    signalSent = signal || null;
    return new Promise<ChatResponse>(() => {});
  });

  const { rerender } = render(<ChatPanel role="fan" language="en" />);

  const input = screen.getByPlaceholderText("Ask as Fan…") as HTMLInputElement;
  const form = screen.getByPlaceholderText("Ask as Fan…").closest("form")!;

  fireEvent.change(input, { target: { value: "Hello fan" } });
  fireEvent.submit(form);

  expect(mockedSendChat).toHaveBeenCalledTimes(1);
  expect(signalSent).not.toBeNull();
  expect(signalSent!.aborted).toBe(false);

  // Rerender with a different role to trigger useEffect cleanup
  rerender(<ChatPanel role="volunteer" language="en" />);

  expect(signalSent!.aborted).toBe(true);
});
