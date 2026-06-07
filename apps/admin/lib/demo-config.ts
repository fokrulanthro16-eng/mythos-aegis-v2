export function getProjectId(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("aegis_project_id") ?? "";
}

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("aegis_token") ?? "";
}

export function saveProjectId(id: string): void {
  if (id.trim()) localStorage.setItem("aegis_project_id", id.trim());
  else localStorage.removeItem("aegis_project_id");
}

export function saveToken(t: string): void {
  if (t.trim()) localStorage.setItem("aegis_token", t.trim());
  else localStorage.removeItem("aegis_token");
}

export function isValidUUID(s: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);
}
