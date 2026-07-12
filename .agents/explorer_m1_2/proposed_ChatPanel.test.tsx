import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { ChatPanel } from "../components/ChatPanel";
import { sendChat } from "../api";
import type { ChatResponse } from "../types";

vi.mock("../api");
const mockedSendChat = vi.mocked(sendChat);

test("sends a chat request and displays the reply", async () => {
  const fake: ChatResponse = {
    reply: "The North Gate is open.",
    role: "fan",
    language: "en",
    tool_events: [{ name: "get_gate_status", args: { gate_id: "G-N" }, result: {}, error: false }],
    snapshot_summary: "Match phase: arrival.",
  };
  mockedSendChat.mockResolvedValue(fake);

  render(<ChatPanel role="fan" language="en" />);

  const input = screen.getByPlaceholderText("Ask as fan…") as HTMLInputElement;
  fireEvent.change(input, { target: { value: "How is the North Gate?" } });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => expect(screen.getByText("The North Gate is open.")).toBeInTheDocument());
  expect(mockedSendChat).toHaveBeenCalledWith(
    "How is the North Gate?",
    "fan",
    [],
    "en",
    expect.any(AbortSignal)
  );
  expect(screen.getByText("1 tool call(s)")).toBeInTheDocument();
});

test("shows error message on failure", async () => {
  mockedSendChat.mockRejectedValue(new Error("network down"));
  render(<ChatPanel role="volunteer" language="en" />);
  fireEvent.change(screen.getByPlaceholderText("Ask as volunteer…"), {
    target: { value: "hi" },
  });
  fireEvent.click(screen.getByText("Send"));
  await waitFor(() => expect(screen.getByText(/network down/)).toBeInTheDocument());
});
