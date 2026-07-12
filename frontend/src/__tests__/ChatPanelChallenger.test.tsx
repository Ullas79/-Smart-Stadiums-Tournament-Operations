import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, test, expect, beforeEach } from "vitest";
import { ChatPanel } from "../components/ChatPanel";
import { sendChat } from "../api";
import type { ChatResponse } from "../types";

vi.mock("../api");
const mockedSendChat = vi.mocked(sendChat);

beforeEach(() => {
  vi.resetAllMocks();
});

test("ignores concurrent submissions while a request is in flight", async () => {
  let resolvePromise: (value: ChatResponse) => void = () => {};
  const chatPromise = new Promise<ChatResponse>((resolve) => {
    resolvePromise = resolve;
  });
  mockedSendChat.mockReturnValue(chatPromise);

  render(<ChatPanel role="fan" language="en" />);

  const input = screen.getByPlaceholderText("Ask as fan…") as HTMLInputElement;
  const sendButton = screen.getByText("Send");

  // Type and click send the first time
  fireEvent.change(input, { target: { value: "Hello first" } });
  fireEvent.click(sendButton);

  // Attempt to type and click send again immediately while busy is true
  fireEvent.change(input, { target: { value: "Hello second" } });
  fireEvent.click(sendButton);

  // Assert that sendChat was only called once
  expect(mockedSendChat).toHaveBeenCalledTimes(1);
  expect(mockedSendChat).toHaveBeenCalledWith(
    "Hello first",
    "fan",
    [],
    "en",
    expect.any(AbortSignal)
  );

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

test("aborts in-flight request on role change and does not show error", async () => {
  let signalPassed: AbortSignal | undefined = undefined;
  const chatPromise = new Promise<ChatResponse>((_, reject) => {
    const checkAbort = () => {
      if (signalPassed?.aborted) {
        const err = new Error("aborted");
        err.name = "AbortError";
        reject(err);
      } else {
        setTimeout(checkAbort, 10);
      }
    };
    setTimeout(checkAbort, 10);
  });
  
  mockedSendChat.mockImplementation((_text, _role, _history, _lang, signal) => {
    signalPassed = signal;
    return chatPromise;
  });

  const { rerender } = render(<ChatPanel role="fan" language="en" />);

  const input = screen.getByPlaceholderText("Ask as fan…") as HTMLInputElement;
  const sendButton = screen.getByText("Send");

  fireEvent.change(input, { target: { value: "Cancel me" } });
  fireEvent.click(sendButton);

  expect(mockedSendChat).toHaveBeenCalledTimes(1);
  expect(signalPassed).not.toBeNull();
  expect((signalPassed as any).aborted).toBe(false);

  // Rerender with a different role to trigger cleanup
  rerender(<ChatPanel role="volunteer" language="en" />);

  // The signal should be aborted
  await waitFor(() => expect(signalPassed?.aborted).toBe(true));

  // The pending message should be removed, and no error message should be displayed
  await waitFor(() => {
    expect(screen.queryByText("…")).not.toBeInTheDocument();
    expect(screen.queryByText(/Error/)).not.toBeInTheDocument();
  });
});

test("aborts in-flight request on language change and does not show error", async () => {
  let signalPassed: AbortSignal | undefined = undefined;
  const chatPromise = new Promise<ChatResponse>((_, reject) => {
    const checkAbort = () => {
      if (signalPassed?.aborted) {
        const err = new Error("aborted");
        err.name = "AbortError";
        reject(err);
      } else {
        setTimeout(checkAbort, 10);
      }
    };
    setTimeout(checkAbort, 10);
  });
  
  mockedSendChat.mockImplementation((_text, _role, _history, _lang, signal) => {
    signalPassed = signal;
    return chatPromise;
  });

  const { rerender } = render(<ChatPanel role="fan" language="en" />);

  const input = screen.getByPlaceholderText("Ask as fan…") as HTMLInputElement;
  const sendButton = screen.getByText("Send");

  fireEvent.change(input, { target: { value: "Cancel me on lang change" } });
  fireEvent.click(sendButton);

  expect(mockedSendChat).toHaveBeenCalledTimes(1);
  expect((signalPassed as any).aborted).toBe(false);

  // Rerender with a different language to trigger cleanup
  rerender(<ChatPanel role="fan" language="fr" />);

  // The signal should be aborted
  await waitFor(() => expect(signalPassed?.aborted).toBe(true));

  // The pending message should be removed
  await waitFor(() => {
    expect(screen.queryByText("…")).not.toBeInTheDocument();
    expect(screen.queryByText(/Error/)).not.toBeInTheDocument();
  });
});
