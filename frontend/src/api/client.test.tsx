// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { request, useApi } from "./client";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("API transport", () => {
  it("surfaces structured backend errors instead of substituting data", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { error: { message: "Historical snapshot unavailable." } },
            { status: 503 },
          ),
        ),
    );
    await expect(request("/overview")).rejects.toThrow(
      "Historical snapshot unavailable.",
    );
  });
  it("reports network failure clearly", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("network error")),
    );
    await expect(request("/overview")).rejects.toThrow("could not be reached");
  });
  it("rejects an unreadable success response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>not JSON</html>")),
    );
    await expect(request("/overview")).rejects.toThrow("unreadable response");
  });
});

describe("filter changes and retries", () => {
  it("aborts an older request and ignores its late result", async () => {
    let resolveOld!: (value: Response) => void;
    let oldSignal: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, options: RequestInit) => {
        if (url.endsWith("/first")) {
          oldSignal = options.signal as AbortSignal;
          return new Promise<Response>((resolve) => {
            resolveOld = resolve;
          });
        }
        return Promise.resolve(Response.json({ value: "new" }));
      }),
    );
    const { result, rerender } = renderHook(
      ({ path }) => useApi<{ value: string }>(path),
      { initialProps: { path: "/first" } },
    );
    expect(result.current.loading).toBe(true);
    rerender({ path: "/second" });
    await waitFor(() => expect(result.current.data?.value).toBe("new"));
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => {
      resolveOld(Response.json({ value: "old" }));
    });
    expect(result.current.data?.value).toBe("new");
  });
  it("retries a failed request and clears its error", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json(
            { error: { message: "Temporarily unavailable" } },
            { status: 503 },
          ),
        )
        .mockResolvedValueOnce(Response.json({ matched_hours: 0 })),
    );
    const { result } = renderHook(() =>
      useApi<{ matched_hours: number }>("/overview"),
    );
    await waitFor(() =>
      expect(result.current.error).toBe("Temporarily unavailable"),
    );
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data?.matched_hours).toBe(0));
    expect(result.current.error).toBeUndefined();
  });
});
