export type TenantHealth = "healthy" | "degraded" | "critical";
export type EventSeverity = "critical" | "high" | "medium" | "low" | "info";
export type EventType =
  | "jwt_failure"
  | "rbac_denial"
  | "sql_block"
  | "rate_limit"
  | "health_change"
  | "secret_rotation"
  | "tenant_isolation"
  | "auth_success";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  health: TenantHealth;
  healthScore: number;
  requestsToday: number;
  requestsLastHour: number;
  activeUsers: number;
  isolationStatus: "strict" | "soft" | "monitoring";
  riskScore: number;
  plan: "enterprise" | "business" | "growth";
  region: string;
  lastActivity: Date;
  sqlQueriesBlocked: number;
  rbacDenials: number;
  jwtFailures: number;
}

export interface SecurityEvent {
  id: string;
  type: EventType;
  severity: EventSeverity;
  message: string;
  detail: string;
  tenant: string;
  ip?: string;
  userId?: string;
  timestamp: Date;
  resolved: boolean;
}

export interface SqlQuery {
  id: string;
  status: "allowed" | "blocked" | "rewritten";
  blockedAt?: string;
  original: string;
  transformed?: string;
  reason?: string;
  tenant: string;
  timestamp: Date;
  durationMs?: number;
  rowsReturned?: number;
  stagesCompleted: number;
}

export interface MetricPoint {
  time: string;
  alpha: number;
  beta: number;
  gamma: number;
  total: number;
}

export interface LatencyPoint {
  time: string;
  p50: number;
  p95: number;
  p99: number;
}

export interface ThreatCategory {
  category: string;
  value: number;
  fullMark: number;
  count: number;
}

// ── Tenants ───────────────────────────────────────────────────────────────────

export const tenants: Tenant[] = [
  {
    id: "tenant-alpha",
    name: "Alpha Industries",
    slug: "alpha",
    health: "healthy",
    healthScore: 98.4,
    requestsToday: 12847,
    requestsLastHour: 847,
    activeUsers: 234,
    isolationStatus: "strict",
    riskScore: 12,
    plan: "enterprise",
    region: "us-east-1",
    lastActivity: new Date(Date.now() - 1000 * 90),
    sqlQueriesBlocked: 3,
    rbacDenials: 7,
    jwtFailures: 2,
  },
  {
    id: "tenant-beta",
    name: "Beta Corp",
    slug: "beta",
    health: "degraded",
    healthScore: 94.1,
    requestsToday: 8234,
    requestsLastHour: 312,
    activeUsers: 89,
    isolationStatus: "strict",
    riskScore: 34,
    plan: "business",
    region: "eu-west-1",
    lastActivity: new Date(Date.now() - 1000 * 45),
    sqlQueriesBlocked: 12,
    rbacDenials: 19,
    jwtFailures: 8,
  },
  {
    id: "tenant-gamma",
    name: "Gamma Labs",
    slug: "gamma",
    health: "healthy",
    healthScore: 99.2,
    requestsToday: 3421,
    requestsLastHour: 178,
    activeUsers: 41,
    isolationStatus: "monitoring",
    riskScore: 6,
    plan: "growth",
    region: "ap-southeast-1",
    lastActivity: new Date(Date.now() - 1000 * 12),
    sqlQueriesBlocked: 0,
    rbacDenials: 2,
    jwtFailures: 0,
  },
];

// ── Security Events ───────────────────────────────────────────────────────────

export const securityEvents: SecurityEvent[] = [
  {
    id: "evt-001",
    type: "jwt_failure",
    severity: "high",
    message: "JWT signature verification failed",
    detail: "Algorithm mismatch: expected HS256, got RS256",
    tenant: "beta",
    ip: "203.0.113.47",
    userId: "usr_7f3a9d",
    timestamp: new Date(Date.now() - 1000 * 28),
    resolved: false,
  },
  {
    id: "evt-002",
    type: "sql_block",
    severity: "medium",
    message: "SQL Airlock blocked query",
    detail: "SELECT * is not permitted — explicit columns required",
    tenant: "beta",
    userId: "usr_2c8f1e",
    timestamp: new Date(Date.now() - 1000 * 63),
    resolved: true,
  },
  {
    id: "evt-003",
    type: "rate_limit",
    severity: "medium",
    message: "Rate limit exceeded — WRITE_MUTATION policy",
    detail: "23 requests in 60s, limit is 20. User suspended 60s.",
    tenant: "alpha",
    userId: "usr_9a4b2c",
    timestamp: new Date(Date.now() - 1000 * 112),
    resolved: true,
  },
  {
    id: "evt-004",
    type: "rbac_denial",
    severity: "high",
    message: "RBAC permission denied",
    detail: "Required: analytics.write — user has: analytics.read",
    tenant: "beta",
    userId: "usr_1d5f8a",
    timestamp: new Date(Date.now() - 1000 * 187),
    resolved: false,
  },
  {
    id: "evt-005",
    type: "secret_rotation",
    severity: "info",
    message: "JWT signing key rotated successfully",
    detail: "Previous key retained for 3600s grace period",
    tenant: "alpha",
    timestamp: new Date(Date.now() - 1000 * 60 * 14),
    resolved: true,
  },
  {
    id: "evt-006",
    type: "tenant_isolation",
    severity: "critical",
    message: "Cross-tenant data access attempt blocked",
    detail: "Query contained tenant_id='alpha', request authenticated as beta",
    tenant: "beta",
    userId: "usr_8e2d4f",
    ip: "198.51.100.23",
    timestamp: new Date(Date.now() - 1000 * 60 * 22),
    resolved: true,
  },
  {
    id: "evt-007",
    type: "jwt_failure",
    severity: "medium",
    message: "Expired token presented",
    detail: "Token expired 847s ago. Issued at 2026-06-06T04:12:00Z.",
    tenant: "gamma",
    userId: "usr_3b7c9e",
    timestamp: new Date(Date.now() - 1000 * 60 * 31),
    resolved: true,
  },
  {
    id: "evt-008",
    type: "auth_success",
    severity: "info",
    message: "New session authenticated",
    detail: "MFA verified. 2FA TOTP method.",
    tenant: "alpha",
    userId: "usr_5f1a8d",
    timestamp: new Date(Date.now() - 1000 * 60 * 3),
    resolved: true,
  },
  {
    id: "evt-009",
    type: "sql_block",
    severity: "high",
    message: "SQL injection attempt blocked",
    detail: "AST parser rejected UNION SELECT with subquery depth > 2",
    tenant: "beta",
    ip: "10.0.2.88",
    timestamp: new Date(Date.now() - 1000 * 60 * 47),
    resolved: true,
  },
  {
    id: "evt-010",
    type: "rate_limit",
    severity: "low",
    message: "SQL_ANALYTICS policy — soft limit warning",
    detail: "48/60 queries used in this window. 80% threshold reached.",
    tenant: "alpha",
    userId: "usr_0c3e7b",
    timestamp: new Date(Date.now() - 1000 * 60 * 8),
    resolved: true,
  },
];

// ── SQL Queries ───────────────────────────────────────────────────────────────

export const sqlQueries: SqlQuery[] = [
  {
    id: "sql-001",
    status: "blocked",
    blockedAt: "AST Parse",
    original: "SELECT * FROM users WHERE 1=1",
    reason: "SELECT * is not permitted — explicit column list required",
    tenant: "beta",
    timestamp: new Date(Date.now() - 1000 * 63),
    stagesCompleted: 2,
  },
  {
    id: "sql-002",
    status: "allowed",
    original:
      "SELECT id, email, created_at FROM orders WHERE created_at > NOW() - INTERVAL '30 days' LIMIT 50",
    transformed:
      "SELECT id, email, created_at FROM orders WHERE tenant_id = 'alpha' AND created_at > NOW() - INTERVAL '30 days' LIMIT 50",
    tenant: "alpha",
    timestamp: new Date(Date.now() - 1000 * 120),
    durationMs: 18,
    rowsReturned: 50,
    stagesCompleted: 7,
  },
  {
    id: "sql-003",
    status: "blocked",
    blockedAt: "Tenant Inject",
    original:
      "SELECT id, amount FROM orders WHERE tenant_id = 'alpha' AND status = 'paid'",
    reason:
      "Manual tenant_id injection not permitted — framework handles isolation",
    tenant: "beta",
    timestamp: new Date(Date.now() - 1000 * 60 * 47),
    stagesCompleted: 3,
  },
  {
    id: "sql-004",
    status: "rewritten",
    original:
      "SELECT product_id, SUM(quantity) FROM order_items GROUP BY product_id ORDER BY SUM(quantity) DESC",
    transformed:
      "SELECT product_id, SUM(quantity) FROM order_items WHERE tenant_id = 'gamma' GROUP BY product_id ORDER BY SUM(quantity) DESC LIMIT 100",
    tenant: "gamma",
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
    durationMs: 34,
    rowsReturned: 87,
    stagesCompleted: 7,
  },
  {
    id: "sql-005",
    status: "blocked",
    blockedAt: "AST Parse",
    original:
      "SELECT u.id FROM users u JOIN (SELECT id FROM admins WHERE 1=1) a ON u.id = a.id",
    reason: "Subquery depth exceeds maximum (2). AST validation failed.",
    tenant: "beta",
    timestamp: new Date(Date.now() - 1000 * 60 * 47),
    stagesCompleted: 2,
  },
  {
    id: "sql-006",
    status: "allowed",
    original:
      "SELECT id, name, status FROM products WHERE status = 'active' ORDER BY name LIMIT 20",
    transformed:
      "SELECT id, name, status FROM products WHERE tenant_id = 'alpha' AND status = 'active' ORDER BY name LIMIT 20",
    tenant: "alpha",
    timestamp: new Date(Date.now() - 1000 * 60 * 2),
    durationMs: 9,
    rowsReturned: 20,
    stagesCompleted: 7,
  },
];

// ── Threat Radar Data ─────────────────────────────────────────────────────────

export const threatData: ThreatCategory[] = [
  { category: "JWT Failures", value: 23, fullMark: 100, count: 10 },
  { category: "Rate Limits", value: 41, fullMark: 100, count: 18 },
  { category: "RBAC Denials", value: 28, fullMark: 100, count: 28 },
  { category: "SQL Blocks", value: 52, fullMark: 100, count: 15 },
  { category: "Isolation", value: 8, fullMark: 100, count: 3 },
  { category: "Secret Events", value: 15, fullMark: 100, count: 5 },
];

// ── Time Series ───────────────────────────────────────────────────────────────

function generateHours(count: number): MetricPoint[] {
  return Array.from({ length: count }, (_, i) => {
    const h = new Date(Date.now() - (count - 1 - i) * 60 * 60 * 1000);
    const base = 300 + Math.sin(i * 0.5) * 100;
    return {
      time: h.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }),
      alpha: Math.floor(base * 1.8 + Math.random() * 120),
      beta: Math.floor(base * 1.1 + Math.random() * 80),
      gamma: Math.floor(base * 0.5 + Math.random() * 40),
      total: Math.floor(base * 3.4 + Math.random() * 200),
    };
  });
}

export const requestVolumeData: MetricPoint[] = generateHours(24);

export const latencyData: LatencyPoint[] = Array.from({ length: 24 }, (_, i) => {
  const h = new Date(Date.now() - (23 - i) * 60 * 60 * 1000);
  return {
    time: h.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }),
    p50: Math.floor(12 + Math.random() * 8),
    p95: Math.floor(45 + Math.random() * 30),
    p99: Math.floor(120 + Math.random() * 80),
  };
});

export const sparkline7d = Array.from({ length: 14 }, () => Math.floor(Math.random() * 100));

// ── System Status ─────────────────────────────────────────────────────────────

export const systemStatus = {
  overall: "operational" as "operational" | "degraded" | "incident",
  riskScore: 24,
  activePolicies: 47,
  tenantsProtected: 3,
  requestsLast24h: 24502,
  avgLatencyMs: 18,
  uptimePercent: 99.97,
  sqlBlocksToday: 15,
  jwtFailuresToday: 10,
  rbacDenialsToday: 28,
};

// ── Command Palette Items ─────────────────────────────────────────────────────

export const commandItems = [
  { id: "cmd-1", group: "Navigate", label: "Open Command Center", href: "/console" },
  { id: "cmd-2", group: "Navigate", label: "Open SQL Airlock", href: "/console/airlock" },
  { id: "cmd-3", group: "Navigate", label: "Open Security Events", href: "/console/security" },
  { id: "cmd-4", group: "Navigate", label: "Open Tenant Intelligence", href: "/console/tenants" },
  { id: "cmd-5", group: "Navigate", label: "Open Observability", href: "/console/observability" },
  { id: "cmd-6", group: "Navigate", label: "Open Settings", href: "/console/settings" },
  { id: "cmd-7", group: "Tenants", label: "View Alpha Industries", href: "/console/tenants" },
  { id: "cmd-8", group: "Tenants", label: "View Beta Corp", href: "/console/tenants" },
  { id: "cmd-9", group: "Tenants", label: "View Gamma Labs", href: "/console/tenants" },
  { id: "cmd-10", group: "Actions", label: "Rotate JWT Key — Alpha Industries", href: "/console/settings" },
  { id: "cmd-11", group: "Actions", label: "Check System Health", href: "/console/observability" },
  { id: "cmd-12", group: "Actions", label: "View SQL Block Log", href: "/console/airlock" },
  { id: "cmd-13", group: "Security", label: "View Recent JWT Failures", href: "/console/security" },
  { id: "cmd-14", group: "Security", label: "View RBAC Denial Report", href: "/console/security" },
  { id: "cmd-15", group: "Security", label: "View Cross-Tenant Attempts", href: "/console/security" },
];
