"""Prometheus metrics for Mythos Aegis.

Label discipline
----------------
- Labels are coarse-grained: method, endpoint (normalised path), status_code,
  pathway, failure_type, reason.
- High-cardinality fields (user_id, tenant_id, request body, raw path params)
  are NEVER used as labels.
- All metric names use the `mythos_` prefix for easy scoping.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# ── HTTP layer ────────────────────────────────────────────────────────────────

http_requests_total = Counter(
    "mythos_http_requests_total",
    "Total number of HTTP requests received",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "mythos_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Pathway routing ───────────────────────────────────────────────────────────

pathway_requests_total = Counter(
    "mythos_pathway_requests_total",
    "Requests dispatched to each execution pathway",
    ["pathway"],  # write | sql_analytics | rag_vision | clarification | noop
)

# ── SQL Airlock ───────────────────────────────────────────────────────────────

sql_airlock_rejections_total = Counter(
    "mythos_sql_airlock_rejections_total",
    "Queries rejected by the SQL Airlock validator",
    ["reason"],  # e.g. forbidden_table | forbidden_column | no_select | etc.
)

# ── Authentication / authorisation ────────────────────────────────────────────

auth_failures_total = Counter(
    "mythos_auth_failures_total",
    "Authentication and authorisation failures",
    [
        "failure_type"
    ],  # missing_token | expired_token | invalid_token | insufficient_permission
)

# ── Intent parser ─────────────────────────────────────────────────────────────

clarification_requests_total = Counter(
    "mythos_clarification_requests_total",
    "Requests routed to CLARIFICATION due to low confidence or ambiguous intent",
)

# ── Error boundary ────────────────────────────────────────────────────────────

unhandled_errors_total = Counter(
    "mythos_unhandled_errors_total",
    "Unexpected errors caught by the orchestrator global exception boundary",
)

# ── Rate limiting ─────────────────────────────────────────────────────────────

rate_limit_hits_total = Counter(
    "mythos_rate_limit_hits_total",
    "Total rate-limit checks performed (allowed + blocked)",
    ["policy"],  # anon | auth | sql | write | vision
)

rate_limit_blocks_total = Counter(
    "mythos_rate_limit_blocks_total",
    "Requests rejected by the rate limiter (HTTP 429 responses)",
    ["policy"],
)

# ── Secrets management ────────────────────────────────────────────────────────

secret_validation_failures_total = Counter(
    "mythos_secret_validation_failures_total",
    "Secret validation failures (production strength enforcement)",
    ["reason"],  # missing | too_short | default_value
)

secret_rotation_total = Counter(
    "mythos_secret_rotation_total",
    "JWT signing key rotation events",
    ["event"],  # promoted | retired
)

# ── AI Gateway ────────────────────────────────────────────────────────────────

ai_requests_total = Counter(
    "mythos_ai_requests_total",
    "Total AI provider requests",
    ["provider", "task_type"],
)

ai_failures_total = Counter(
    "mythos_ai_failures_total",
    "AI provider request failures",
    ["provider", "failure_type"],
)

ai_tokens_total = Counter(
    "mythos_ai_tokens_total",
    "Total tokens consumed by AI provider calls",
    ["provider", "token_type"],  # token_type: input | output
)

ai_cost_total = Counter(
    "mythos_ai_cost_total",
    "Estimated AI cost in USD (accumulated)",
    ["provider"],
)

# ── RAG pipeline ──────────────────────────────────────────────────────────────

rag_documents_indexed_total = Counter(
    "mythos_rag_documents_indexed_total",
    "Documents successfully indexed into the RAG store",
    ["tenant_id"],
)

rag_search_requests_total = Counter(
    "mythos_rag_search_requests_total",
    "Semantic search queries executed",
    ["tenant_id"],
)

# ── Workflow Engine ───────────────────────────────────────────────────────────

workflow_executions_total = Counter(
    "mythos_workflow_executions_total",
    "Total workflow execution attempts",
    ["status"],  # completed | failed | cancelled
)

workflow_step_executions_total = Counter(
    "mythos_workflow_step_executions_total",
    "Total workflow step execution attempts",
    ["step_type", "status"],  # step_type: agent_task | rag_search | ...
)

workflow_execution_duration_seconds = Histogram(
    "mythos_workflow_execution_duration_seconds",
    "End-to-end workflow execution latency in seconds",
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0),
)

# ── Billing ───────────────────────────────────────────────────────────────────

billing_checkouts_total = Counter(
    "mythos_billing_checkouts_total",
    "Checkout sessions created",
    ["plan"],  # free | pro | business | enterprise
)

billing_subscriptions_total = Counter(
    "mythos_billing_subscriptions_total",
    "Subscription state transitions",
    ["plan", "status"],  # status: active | cancelled | past_due
)

quota_checks_total = Counter(
    "mythos_quota_checks_total",
    "Quota enforcement checks",
    ["feature", "result"],  # result: allowed | denied
)
