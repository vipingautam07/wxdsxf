import { useEffect, useState } from "react";

const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export function endpoint(path: string, parameters: Record<string, string>) {
  return `${path}?${new URLSearchParams(parameters)}`;
}

export async function request<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error(
      "The data service could not be reached. Check the connection and try again.",
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      body?.error?.message ||
        body?.issue ||
        `Data service returned ${response.status}.`,
    );
  if (!body)
    throw new Error("The data service returned an unreadable response.");
  return body as T;
}

export function useApi<T>(path: string) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    key: string;
    data?: T;
    error?: string;
    loading: boolean;
  }>({ key: "", loading: true });
  useEffect(() => {
    const controller = new AbortController();
    setState({ key: path, loading: true });
    request<T>(path, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted)
          setState({ key: path, data, loading: false });
      },
      (error) => {
        if (!controller.signal.aborted)
          setState({ key: path, error: String(error.message), loading: false });
      },
    );
    return () => controller.abort();
  }, [path, attempt]);
  return {
    data: state.key === path ? state.data : undefined,
    error: state.key === path ? state.error : undefined,
    loading: state.key !== path || state.loading,
    retry: () => setAttempt((a) => a + 1),
  };
}
