# Optimization Analysis & Recommendations Report (Milestone 13 R3)

This report details the audit of React components and Vite bundle configurations for optimization. All proposed optimized files have been written as replacement files in `.agents/explorer_opt_3/`.

---

## 1. Observation

### Current Rendering and State Behavior:
* **`frontend/src/App.tsx` (Lines 17-33)**:
  ```tsx
  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const s = await fetchState();
        if (active) setSnapshot(s);
      } catch {
        /* backend not up yet */
      }
    }
    poll();
    const id = setInterval(poll, 1500);
    ...
  ```
  A poll runs every 1.5 seconds, retrieving a new `StadiumSnapshot` object reference. Even when the stadium data is unchanged, calling `setSnapshot(s)` with a new object reference triggers a full re-render of `App` every 1.5 seconds.
* **Child Component Behavior**:
  * **`RoleSwitcher`** (`RoleSwitcher.tsx:16`): Re-renders on every poll because its parent `App` re-renders, despite its props (`role` and `onChange`) remaining unchanged.
  * **`ChatPanel`** (`ChatPanel.tsx:39`): Re-renders on every poll despite having no dependency on `snapshot`.
  * **`ScenarioPanel`** (`ScenarioPanel.tsx:5`): Re-renders on every poll despite having no props at all.
  * **`OpsDashboard`** (`OpsDashboard.tsx:18`): Re-renders on every poll. Even if `React.memo` is used, the shallow equality check fails since `snapshot` is a new object reference on every poll.

### Component Event Handlers & Local State:
* **`ChatPanel.tsx` (Lines 52-75)**:
  * The `submit` function is re-created on every single render. When typing in the chat input, `input` state updates on every keystroke, causing `ChatPanel` to re-render and re-create `submit`.
  * The form submit action uses an inline callback:
    ```tsx
    onSubmit={(e) => {
      e.preventDefault();
      submit(input).catch((err) => { ... });
    }}
    ```
* **`ScenarioPanel.tsx` (Lines 9-41)**:
  * The `handleTrigger` function is re-created on every render.

### Bundle Structure and Configurations:
* **`package.json`**:
  Currently includes only `react` and `react-dom` in `dependencies`.
* **`vite.config.ts`**:
  Does not contain any `build.rollupOptions` or `manualChunks` configurations.
* **Baseline Production Build**:
  Running `npm run build` bundles all code into a single Javascript chunk:
  `dist/assets/index-DyXxKAkf.js   151.72 kB`

---

## 2. Logic Chain

1. **Eliminate Poll-Driven Render Cascades**:
   * Since `snapshot` is fetched as a fresh object reference, we can prevent `App` (and therefore all children) from re-rendering when the polled data hasn't changed. By checking `JSON.stringify(prev) === JSON.stringify(s)` inside the state updater `setSnapshot`, React will bail out of the update if the snapshot content is identical.
2. **Prevent Child Re-Renders via `React.memo`**:
   * Wrapping `ChatPanel`, `ScenarioPanel`, and `RoleSwitcher` in `React.memo` prevents them from re-rendering when the parent `App` does re-render (e.g. when `snapshot` actually changes, or when language/role changes). Since their inputs are reference-stable (`role`, `language`, and `setRole` dispatch function), they will only re-render when they truly need to.
   * Wrapping `OpsDashboard` in `React.memo` with a custom comparison function (comparing `JSON.stringify(prev.snapshot) === JSON.stringify(next.snapshot)`) ensures it only re-renders when the stadium data actually changes.
3. **Stabilize Event Handlers via `useCallback`**:
   * Wrapping `submit` in `useCallback` in `ChatPanel.tsx` and memoizing `handleSubmit` prevents handler re-creation during keystroke-driven input updates.
   * Wrapping `handleTrigger` in `useCallback(..., [])` in `ScenarioPanel.tsx` avoids re-creating the function when loading or feedback states change.
4. **Vite Bundle Splitting**:
   * Configuring `manualChunks` under `build.rollupOptions.output` allows splitting React core (`react`, `react-dom`, `scheduler`), third-party libraries (e.g. `lucide-react`, `recharts` if introduced), and general vendor dependencies into separate chunks.
   * This improves Time to Interactive (TTI) and leverages browser caching, as changes to application code won't invalidate cached third-party libraries.

---

## 3. Caveats

* **JSON Serialization for Deep Equality**:
  Using `JSON.stringify` for deep comparison is safe and performant here because the `StadiumSnapshot` object is small, shallow, contains no circular references, and contains only primitive/array/object types that serialize deterministically.
* **Potential Future Dependencies**:
  The chunk splitting rules for `lucide-react` and `recharts` are defined proactively. They will split these packages into their own chunks automatically if they are added to the project in the future.

---

## 4. Conclusion

Implementing the proposed memoizations and chunk-splitting configuration will:
1. Eliminate unnecessary re-renders of the chat, role switcher, and scenario panels during live-polling.
2. Eliminate re-renders of the dashboard when live data is unchanged.
3. Avoid re-creation of event handlers on user keystrokes in the chat.
4. Split the single `151.72 kB` bundle into optimized chunks (e.g. `vendor-react` and `index` application bundle), maximizing browser caching.

---

## 5. Proposed Code Edits

The detailed edits are provided below and correspond to the replacement files located in `.agents/explorer_opt_3/`.

### A. `frontend/src/App.tsx`
* **Path**: `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\frontend\src\App.tsx`
* **Edit**: Prevent re-render if snapshot content is unchanged.
* **Snippet**:
```tsx
// Before (Lines 22):
if (active) setSnapshot(s);

// After:
if (active) {
  setSnapshot((prev) => {
    // Avoid triggering re-render if snapshot data is identical
    if (JSON.stringify(prev) === JSON.stringify(s)) {
      return prev;
    }
    return s;
  });
}
```

### B. `frontend/src/components/RoleSwitcher.tsx`
* **Path**: `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\frontend\src\components\RoleSwitcher.tsx`
* **Edit**: Wrap in `React.memo`.
* **Snippet**:
```tsx
// Before (Lines 16):
export function RoleSwitcher({ role, onChange }: Props) {

// After:
import { memo } from "react";
// ...
export const RoleSwitcher = memo(function RoleSwitcher({ role, onChange }: Props) {
  // ...
});
```

### C. `frontend/src/components/ChatPanel.tsx`
* **Path**: `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\frontend\src\components\ChatPanel.tsx`
* **Edit**: Wrap in `React.memo`, memoize `submit` and `handleSubmit` using `useCallback`.
* **Snippet**:
```tsx
// Before (Lines 1-4, 39, 52-75, 125-133):
import { useState, useRef, useEffect } from "react";
// ...
export function ChatPanel({ role, language }: Props) {
  // ...
  async function submit(text: string) { ... }
  // ...
  <form className="chat-input" onSubmit={(e) => { e.preventDefault(); submit(input).catch(...) }}>

// After:
import { useState, useRef, useEffect, useCallback, memo } from "react";
// ...
export const ChatPanel = memo(function ChatPanel({ role, language }: Props) {
  // ...
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
  // ...
  <form className="chat-input" onSubmit={handleSubmit}>
```

### D. `frontend/src/components/ScenarioPanel.tsx`
* **Path**: `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\frontend\src\components\ScenarioPanel.tsx`
* **Edit**: Wrap in `React.memo`, memoize `handleTrigger` using `useCallback`.
* **Snippet**:
```tsx
// Before (Lines 1, 5, 9):
import { useState } from "react";
// ...
export function ScenarioPanel() {
  // ...
  const handleTrigger = async (scenario: string) => { ... };

// After:
import { useState, useCallback, memo } from "react";
// ...
export const ScenarioPanel = memo(function ScenarioPanel() {
  // ...
  const handleTrigger = useCallback(async (scenario: string) => {
    // (body remains same)
  }, []);
```

### E. `frontend/src/components/OpsDashboard.tsx`
* **Path**: `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\frontend\src\components\OpsDashboard.tsx`
* **Edit**: Wrap in `React.memo` with a custom comparison function checking deep equality.
* **Snippet**:
```tsx
// Before (Lines 18):
export function OpsDashboard({ snapshot }: Props) {

// After:
import { memo } from "react";
// ...
export const OpsDashboard = memo(
  function OpsDashboard({ snapshot }: Props) {
    // (body remains same)
  },
  (prev, next) => {
    if (prev.snapshot === next.snapshot) return true;
    if (!prev.snapshot || !next.snapshot) return false;
    return JSON.stringify(prev.snapshot) === JSON.stringify(next.snapshot);
  }
);
```

### F. `frontend/vite.config.ts`
* **Path**: `C:\Users\hp\-Smart-Stadiums-Tournament-Operations\frontend\vite.config.ts`
* **Edit**: Configure `manualChunks` in `build.rollupOptions.output`.
* **Snippet**:
```tsx
// Add the build configuration:
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            // Group React core vendor files
            if (
              id.includes("react/") ||
              id.includes("react-dom/") ||
              id.includes("scheduler/")
            ) {
              return "vendor-react";
            }
            // Group Lucide icons (if any are introduced)
            if (id.includes("lucide-react")) {
              return "vendor-lucide";
            }
            // Group heavy charting packages like Recharts or D3
            if (
              id.includes("recharts") ||
              id.includes("d3")
            ) {
              return "vendor-charts";
            }
            // Fallback for all other third-party vendor dependencies
            return "vendor";
          }
        },
      },
    },
  },
```

---

## 6. Verification Method

1. **Verify Compilation and Test Pass**:
   * Execute `npm run test` in `frontend/` to run all test suites and ensure no syntax or render regression occurs.
2. **Verify Production Build & Chunk Splitting**:
   * Execute `npm run build` in `frontend/`.
   * Confirm that the build output splits the React core files out into `dist/assets/vendor-react-XXXX.js`, keeping the main bundle size smaller and TTI lower.
