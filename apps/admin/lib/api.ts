const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("aegis_token");
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<{ data: T | null; error: string | null }> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(options.headers as Record<string, string> | undefined ?? {}),
      },
    });
    if (!res.ok) {
      const text = await res.text();
      let msg = `${res.status} ${res.statusText}`;
      try {
        const parsed = JSON.parse(text);
        if (parsed.detail) msg = parsed.detail;
      } catch {}
      return { data: null, error: msg };
    }
    const data: T = await res.json();
    return { data, error: null };
  } catch (e) {
    return { data: null, error: (e as Error).message };
  }
}

export async function apiUpload<T>(
  path: string,
  form: FormData
): Promise<{ data: T | null; error: string | null }> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    if (!res.ok) {
      const text = await res.text();
      let msg = `${res.status} ${res.statusText}`;
      try {
        const parsed = JSON.parse(text);
        if (parsed.detail) msg = parsed.detail;
      } catch {}
      return { data: null, error: msg };
    }
    const data: T = await res.json();
    return { data, error: null };
  } catch (e) {
    return { data: null, error: (e as Error).message };
  }
}
