import { useState, useCallback, useRef } from "react";

/**
 * React hook for consuming an SSE (Server-Sent Events) stream.
 *
 * Returns:
 *  - streamedText: the accumulated text received so far
 *  - isStreaming: whether a stream is currently active
 *  - startStream: function to kick off a new stream
 *  - cancelStream: function to abort the current stream
 */
export function useStream() {
  const [streamedText, setStreamedText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const controllerRef = useRef(null);

  const cancelStream = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const startStream = useCallback(
    async (url, body) => {
      cancelStream();
      setStreamedText("");
      setIsStreaming(true);

      const controller = new AbortController();
      controllerRef.current = controller;

      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE lines
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            const data = line.slice(5).trim();
            if (!data) continue;

            try {
              const parsed = JSON.parse(data);
              if (parsed.done) {
                setIsStreaming(false);
                return;
              }
              if (parsed.content) {
                setStreamedText((prev) => prev + parsed.content);
              }
            } catch {
              // Skip malformed JSON chunks
            }
          }
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          console.error("Stream error:", err);
        }
      } finally {
        setIsStreaming(false);
        controllerRef.current = null;
      }
    },
    [cancelStream]
  );

  return { streamedText, isStreaming, startStream, cancelStream };
}
