from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any

from flask import Flask, jsonify, render_template, request


PIPELINE_STEPS = [
    "data_ingestion",
    "context_enrichment",
    "signal_normalization",
    "evidence_correlation",
    "historical_retrieval",
    "llm_reasoning_guardrailed",
    "confidence_scoring",
    "rca_decision_generation",
    "recommendation_generation",
]


AGENT_CATALOG = [
    {
        "name": "RCA Orchestrator Agent",
        "responsibilities": [
            "Owns workflow orchestration and evidence routing",
            "Selects specialist agents based on available signals",
            "Produces the final explainable RCA decision",
        ],
        "inputs": ["issue metadata", "telemetry availability", "historical matches"],
        "outputs": ["execution plan", "agent fan-out plan", "final RCA summary"],
        "reasoning_flow": [
            "Validate payload completeness",
            "Select specialist agents",
            "Merge correlated evidence",
            "Escalate low-confidence cases for human review",
        ],
        "implementation": "Temporal or LangGraph-driven orchestrator with evented hand-offs",
    },
    {
        "name": "Defect Analysis Agent",
        "responsibilities": [
            "Classifies defect intent and affected components",
            "Extracts symptom keywords from issue narratives",
        ],
        "inputs": ["jira defect", "test results", "stack traces"],
        "outputs": ["defect taxonomy", "impacted components", "defect evidence"],
        "reasoning_flow": [
            "Normalize defect summary",
            "Detect category features",
            "Link defect symptoms to known failure modes",
        ],
        "implementation": "Rule-based classifier + guarded LLM summarization",
    },
    {
        "name": "Log Analysis Agent",
        "responsibilities": [
            "Parses application, Kubernetes, and observability logs",
            "Finds anomalies, repeated errors, and causal spikes",
        ],
        "inputs": ["application logs", "kubernetes logs", "splunk/datadog traces"],
        "outputs": ["error clusters", "timeline anomalies", "log evidence"],
        "reasoning_flow": [
            "Normalize timestamps",
            "Group errors and traces",
            "Detect dominant failure signatures",
        ],
        "implementation": "Streaming parsers + vectorized log signature clustering",
    },
    {
        "name": "API Analysis Agent",
        "responsibilities": [
            "Detects contract breaks, payload drift, and auth/API failures",
            "Correlates status codes with deployment and schema changes",
        ],
        "inputs": ["api payloads", "response codes", "contract metadata"],
        "outputs": ["api failure diagnosis", "schema drift evidence"],
        "reasoning_flow": [
            "Inspect payload schema deltas",
            "Map response codes to failure modes",
            "Correlate with recent release changes",
        ],
        "implementation": "Schema diff rules + retrieval over API specs",
    },
    {
        "name": "Deployment Analysis Agent",
        "responsibilities": [
            "Examines release metadata, commits, and feature flags",
            "Flags deployment regressions and configuration drift",
        ],
        "inputs": ["deployment changes", "github commits", "feature flags", "ci/cd metadata"],
        "outputs": ["regression candidates", "change risk summary"],
        "reasoning_flow": [
            "Rank recent changes by blast radius",
            "Compare pre/post deploy signals",
            "Identify rollback candidates",
        ],
        "implementation": "Change correlation engine with commit and rollout enrichment",
    },
    {
        "name": "Infra Analysis Agent",
        "responsibilities": [
            "Finds infrastructure bottlenecks, outage signals, and cluster-level regressions",
        ],
        "inputs": ["kubernetes events", "infra logs", "cpu/memory latency signals"],
        "outputs": ["infra diagnosis", "capacity evidence", "affected services"],
        "reasoning_flow": [
            "Correlate node/pod events",
            "Detect saturation or availability failures",
            "Map infra anomalies to user-facing impact",
        ],
        "implementation": "Rules over platform metrics plus anomaly detection",
    },
    {
        "name": "Automation Failure Agent",
        "responsibilities": [
            "Separates true product defects from flaky automation failures",
            "Inspects Playwright, Selenium, and Robot outputs",
        ],
        "inputs": ["playwright logs", "selenium logs", "robot framework output"],
        "outputs": ["automation failure classification", "flakiness indicators"],
        "reasoning_flow": [
            "Parse harness failures",
            "Check environment/test-data coupling",
            "Emit automation remediation hints",
        ],
        "implementation": "Failure signature rules + historical flake patterns",
    },
    {
        "name": "Correlation Agent",
        "responsibilities": [
            "Builds an evidence graph across logs, APIs, deployments, and tests",
            "Scores signal agreement and contradiction",
        ],
        "inputs": ["normalized evidence from specialist agents"],
        "outputs": ["evidence graph", "signal agreement score", "timeline narrative"],
        "reasoning_flow": [
            "Align evidence on a common timeline",
            "Link entities and change events",
            "Emit confidence features for final scoring",
        ],
        "implementation": "Graph-based correlation service with temporal joins",
    },
]


RCA_CATEGORIES = {
    "test automation issue": {
        "keywords": ["playwright", "selenium", "robot framework", "locator", "flaky", "retry"],
        "impacted_systems": ["qa-automation", "test-execution-grid"],
        "remediation": [
            "Stabilize selectors, waits, and test isolation",
            "Quarantine or retry known flaky scenarios behind policy controls",
        ],
        "prevention": [
            "Track flaky signature trends",
            "Enforce test-harness contract checks before merge",
        ],
    },
    "environment issue": {
        "keywords": ["environment", "dns", "network", "ssl", "certificate", "proxy"],
        "impacted_systems": ["test-environment", "shared-services"],
        "remediation": [
            "Validate environment dependencies and connectivity",
            "Re-run health probes before test execution",
        ],
        "prevention": [
            "Add environment readiness gates in CI/CD",
            "Monitor environment drift baselines",
        ],
    },
    "data issue": {
        "keywords": ["seed data", "test data", "null record", "missing record", "duplicate data"],
        "impacted_systems": ["test-data-service", "data-pipelines"],
        "remediation": [
            "Repair or reseed affected datasets",
            "Validate data fixtures before execution",
        ],
        "prevention": [
            "Introduce synthetic data contracts",
            "Version test data with deployment bundles",
        ],
    },
    "api contract issue": {
        "keywords": ["schema", "payload", "400", "422", "contract", "serialization"],
        "impacted_systems": ["api-gateway", "consumer-services"],
        "remediation": [
            "Roll forward or rollback incompatible contract changes",
            "Regenerate client stubs and validate schema compatibility",
        ],
        "prevention": [
            "Enforce contract tests in CI",
            "Publish API compatibility reports on each deployment",
        ],
    },
    "backend logic defect": {
        "keywords": ["500", "nullpointer", "stack trace", "traceback", "exception", "business rule"],
        "impacted_systems": ["application-services", "domain-logic"],
        "remediation": [
            "Patch the failing code path and add regression tests",
            "Instrument failing business rules with richer telemetry",
        ],
        "prevention": [
            "Adopt mutation and property-based tests for critical flows",
            "Add release-time canaries for high-risk services",
        ],
    },
    "infrastructure failure": {
        "keywords": ["kubernetes", "pod", "node", "oom", "disk", "cpu", "memory", "crashloop"],
        "impacted_systems": ["kubernetes-cluster", "platform-runtime"],
        "remediation": [
            "Restore platform capacity or failing infrastructure components",
            "Rebalance or restart impacted workloads with safeguards",
        ],
        "prevention": [
            "Autoscale on saturation indicators",
            "Add SLO-based incident policies for platform dependencies",
        ],
    },
    "authentication issue": {
        "keywords": ["401", "403", "token", "oauth", "sso", "unauthorized", "forbidden"],
        "impacted_systems": ["identity-provider", "auth-gateway"],
        "remediation": [
            "Rotate or repair credentials and auth policies",
            "Validate token audience, issuer, and expiry",
        ],
        "prevention": [
            "Continuously test auth flows against staging and prod-like environments",
            "Alert on abnormal auth rejection rates",
        ],
    },
    "integration failure": {
        "keywords": ["webhook", "queue", "dependency", "downstream", "third party", "connection reset"],
        "impacted_systems": ["integration-layer", "external-dependencies"],
        "remediation": [
            "Re-establish failing integration endpoints",
            "Apply retries, circuit breakers, or fallback behavior",
        ],
        "prevention": [
            "Monitor third-party SLAs and timeout budgets",
            "Test failure injection scenarios on critical integrations",
        ],
    },
    "deployment regression": {
        "keywords": ["deployment", "release", "rollback", "feature flag", "config", "regression"],
        "impacted_systems": ["release-orchestration", "changed-services"],
        "remediation": [
            "Rollback the suspect deployment or disable the feature flag",
            "Compare commit, config, and artifact deltas across the failing window",
        ],
        "prevention": [
            "Adopt progressive delivery with automated blast-radius scoring",
            "Require pre/post deployment quality guardrails",
        ],
    },
    "configuration drift": {
        "keywords": ["configuration", "config drift", "env var", "secret", "mismatch", "toggle"],
        "impacted_systems": ["configuration-management", "runtime-services"],
        "remediation": [
            "Reconcile environment configuration to the expected baseline",
            "Audit secrets, feature flags, and runtime parameters",
        ],
        "prevention": [
            "Continuously diff live config against versioned desired state",
            "Gate deployments on config compliance checks",
        ],
    },
    "performance bottleneck": {
        "keywords": ["latency", "slow", "throughput", "timeout", "performance", "response time"],
        "impacted_systems": ["application-services", "performance-hotspots"],
        "remediation": [
            "Profile and scale the hot path or constrained dependency",
            "Throttle or cache high-volume operations",
        ],
        "prevention": [
            "Run production-like load tests before release",
            "Track saturation, latency, and error budgets together",
        ],
    },
    "dependency outage": {
        "keywords": ["dependency outage", "service unavailable", "503", "vendor", "upstream", "outage"],
        "impacted_systems": ["external-dependencies", "service-mesh"],
        "remediation": [
            "Fail over or isolate the unavailable dependency",
            "Engage dependency-specific incident playbooks",
        ],
        "prevention": [
            "Add graceful degradation paths",
            "Continuously validate dependency health and SLA adherence",
        ],
    },
}


SAMPLE_INCIDENTS = [
    {
        "incident_id": "INC-1007",
        "title": "Checkout failures after payment-service release",
        "category": "deployment regression",
        "tags": ["deployment", "feature flag", "500", "checkout"],
    },
    {
        "incident_id": "INC-1014",
        "title": "Robot suite flakiness due to unstable environment DNS",
        "category": "environment issue",
        "tags": ["robot framework", "dns", "environment", "flaky"],
    },
    {
        "incident_id": "INC-1022",
        "title": "User profile API rejected payload after schema drift",
        "category": "api contract issue",
        "tags": ["api", "schema", "payload", "422"],
    },
    {
        "incident_id": "INC-1033",
        "title": "Kubernetes nodes saturated causing elevated latency",
        "category": "infrastructure failure",
        "tags": ["kubernetes", "cpu", "memory", "latency"],
    },
]


PLATFORM_BLUEPRINT = {
    "improved_architecture": {
        "summary": "Enterprise QA RCA platform built on hybrid intelligence: rules, retrieval, evidence correlation, and guarded LLM reasoning.",
        "layers": [
            "Experience layer: portal, APIs, incident workbench, governance dashboard",
            "Orchestration layer: RCA Orchestrator Agent, Temporal/LangGraph workflows, async event bus",
            "Intelligence layer: specialist agents, rule engine, correlation engine, confidence scoring engine",
            "Knowledge layer: historical incidents, vector search/RAG, runbooks, schema registry",
            "Observability layer: logs, traces, metrics, CI/CD telemetry, deployment intelligence",
            "Platform layer: FastAPI/Flask services, Kafka, Redis, PostgreSQL, Kubernetes, OpenTelemetry",
        ],
        "diagram": [
            "Inputs -> Ingestion API -> Orchestrator -> Specialist Agents -> Correlation Engine",
            "Correlation Engine -> Historical Retrieval + Rule Engine + Guarded LLM",
            "Reasoning Outputs -> Confidence Scoring -> RCA Decision -> Recommendations + Audit Trail",
        ],
    },
    "multi_agent_design": AGENT_CATALOG,
    "processing_pipeline": [
        {"step": "Data ingestion", "details": "Accept Jira defects, test results, logs, traces, deployment metadata, and feature flags."},
        {"step": "Context enrichment", "details": "Pull commits, release windows, ownership metadata, topology, and dependency maps."},
        {"step": "Signal normalization", "details": "Standardize timestamps, severities, sources, entities, and trace/span identifiers."},
        {"step": "Evidence correlation", "details": "Build a timeline and evidence graph across systems, deployments, and test outcomes."},
        {"step": "Historical retrieval", "details": "Retrieve similar incidents, runbooks, and prior remediations from vector and relational stores."},
        {"step": "LLM reasoning", "details": "Use guarded prompts to synthesize evidence instead of inventing facts."},
        {"step": "Confidence scoring", "details": "Blend rule certainty, cross-signal agreement, historical similarity, and data completeness."},
        {"step": "RCA decision generation", "details": "Produce structured RCA with root cause hypotheses, impacted systems, and blast radius."},
        {"step": "Recommendation generation", "details": "Return remediation and preventive actions linked to evidence and policy."},
    ],
    "folder_structure": [
        "app.py",
        "templates/index.html",
        "tests/test_app.py",
        "requirements.txt",
        "Future production folders: agents/, orchestration/, engines/, integrations/, knowledge/, api/, workers/",
    ],
    "api_contracts": [
        {"method": "GET", "path": "/health", "purpose": "Service liveness"},
        {"method": "GET", "path": "/api/v1/blueprint", "purpose": "Enterprise RCA architecture, agents, schemas, roadmap"},
        {"method": "POST", "path": "/api/v1/rca/analyze", "purpose": "Structured RCA analysis from normalized issue context"},
    ],
    "data_models": {
        "issue_payload": {
            "issue_id": "string",
            "title": "string",
            "description": "string",
            "signals": {
                "logs": ["string"],
                "test_results": ["string"],
                "api_payloads": ["string"],
                "ci_metadata": ["string"],
                "deployment_changes": ["string"],
                "feature_flags": ["string"],
            },
            "components": ["string"],
            "environment": "string",
        },
        "rca_output": {
            "category": "string",
            "confidence_score": "float 0..1",
            "probable_root_causes": [{"cause": "string", "confidence": "float"}],
            "impacted_systems": ["string"],
            "historical_matches": [{"incident_id": "string", "similarity": "float"}],
            "recommendations": {"remediation": ["string"], "prevention": ["string"]},
            "explainability": {"rules_triggered": ["string"], "correlated_signals": ["string"]},
        },
    },
    "rca_output_schema": {
        "required_sections": [
            "executive_summary",
            "root_cause_hypotheses",
            "confidence_score",
            "impacted_systems",
            "blast_radius",
            "evidence",
            "recommendations",
            "audit_trail",
        ]
    },
    "confidence_scoring_strategy": {
        "formula": "0.35*rule certainty + 0.25*signal agreement + 0.20*historical similarity + 0.20*input completeness",
        "controls": [
            "Downgrade confidence when specialist agents disagree",
            "Force human review below 0.55 or when evidence conflicts",
            "Persist feature-level confidence inputs for auditability",
        ],
    },
    "technology_recommendations": {
        "api": ["FastAPI for production APIs", "Flask retained here for a lightweight demonstrator"],
        "orchestration": ["Temporal", "LangGraph", "CrewAI for specialist agent coordination"],
        "data": ["PostgreSQL", "Redis", "Kafka", "Pinecone or Weaviate"],
        "observability": ["OpenTelemetry", "ELK", "Datadog", "Prometheus/Grafana"],
        "runtime": ["Docker", "Kubernetes"],
        "models": ["Guarded LLM layer using GPT-class models with policy prompts and tool grounding"],
    },
    "roadmap_phases": [
        "Phase 1: Establish ingestion API, rule engine, and deterministic RCA schema",
        "Phase 2: Add vector retrieval, specialist agents, and deployment/CI correlation",
        "Phase 3: Introduce async orchestration, blast-radius analysis, and self-learning feedback loops",
        "Phase 4: Scale to enterprise tenancy, governance controls, and closed-loop preventive automation",
    ],
    "scalability_considerations": [
        "Separate ingestion from analysis using async queues",
        "Partition historical search and incident storage by tenant",
        "Use streaming log enrichment and cache hot RCA features in Redis",
        "Scale specialist agents independently based on signal volume",
    ],
    "security_recommendations": [
        "RBAC with tenant and environment scoping",
        "Secrets management through cloud KMS or vault integrations",
        "PII redaction before storage or LLM invocation",
        "Signed audit trails for every RCA decision and human override",
    ],
    "example_workflows": [
        "CI failure RCA: failed pipeline -> test logs -> deployment metadata -> code diff -> RCA decision",
        "API failure RCA: 422 spike -> payload drift -> contract diff -> consumer impact -> remediation",
        "Infra incident RCA: pod restarts -> saturation traces -> rollback/noisy neighbor analysis -> blast radius",
    ],
    "agent_prompts": [
        "Defect Analysis Agent prompt: Classify issue taxonomy using only supplied evidence and cite every signal used.",
        "Correlation Agent prompt: Build a timeline of agreeing and contradicting signals; do not infer unsupported events.",
        "RCA Orchestrator prompt: Produce a structured RCA JSON object and flag human review if confidence is below policy threshold.",
    ],
    "production_grade_engineering_recommendations": [
        "Version every prompt, model configuration, and rule set",
        "Record agent inputs/outputs for replay and audit",
        "Adopt schema contracts for external integrations",
        "Use canary releases for agent policy changes",
    ],
}


def _flatten_context(value: Any) -> str:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        return " ".join(_flatten_context(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_context(item) for item in value)
    return str(value).lower()


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_/-]+", text.lower()) if len(token) > 2}


def _historical_matches(tokens: set[str]) -> list[dict[str, Any]]:
    matches = []
    for incident in SAMPLE_INCIDENTS:
        overlap = len(tokens.intersection(set(incident["tags"])))
        if overlap:
            similarity = round(min(0.95, 0.25 + overlap * 0.18), 2)
            matches.append(
                {
                    "incident_id": incident["incident_id"],
                    "title": incident["title"],
                    "category": incident["category"],
                    "similarity": similarity,
                }
            )
    return sorted(matches, key=lambda item: item["similarity"], reverse=True)[:3]


def _pick_agents(payload: dict[str, Any]) -> list[str]:
    agents = ["RCA Orchestrator Agent", "Defect Analysis Agent", "Correlation Agent"]
    signals = payload.get("signals", {})
    signal_text = _flatten_context(signals)
    if any(key in signal_text for key in ["playwright", "selenium", "robot framework", "test"]):
        agents.append("Automation Failure Agent")
    if any(key in signal_text for key in ["log", "trace", "exception", "kubernetes", "splunk", "datadog"]):
        agents.append("Log Analysis Agent")
    if any(key in signal_text for key in ["api", "schema", "payload", "401", "403", "422"]):
        agents.append("API Analysis Agent")
    if any(key in signal_text for key in ["deploy", "release", "commit", "feature flag", "rollback", "config"]):
        agents.append("Deployment Analysis Agent")
    if any(key in signal_text for key in ["pod", "node", "oom", "cpu", "memory", "cluster"]):
        agents.append("Infra Analysis Agent")
    return agents


def _analyze_payload(payload: dict[str, Any]) -> dict[str, Any]:
    combined_text = _flatten_context(payload)
    tokens = _tokenize(combined_text)
    scores: Counter[str] = Counter()
    evidence_by_category: dict[str, list[str]] = {}

    for category, config in RCA_CATEGORIES.items():
        matches = [keyword for keyword in config["keywords"] if keyword in combined_text]
        if matches:
            scores[category] = len(matches)
            evidence_by_category[category] = matches

    if not scores:
        scores["backend logic defect"] = 1
        evidence_by_category["backend logic defect"] = ["defaulted due to incomplete evidence"]

    category, score = scores.most_common(1)[0]
    category_config = RCA_CATEGORIES[category]
    historical_matches = _historical_matches(tokens)
    completeness = min(1.0, 0.2 + (len(tokens) / 40))
    agreement = min(1.0, 0.25 + score / 6)
    history_score = historical_matches[0]["similarity"] if historical_matches else 0.2
    confidence = round(
        min(0.98, 0.35 * min(1.0, score / 4) + 0.25 * agreement + 0.20 * history_score + 0.20 * completeness),
        2,
    )

    components = payload.get("components") or []
    impacted_systems = list(dict.fromkeys(components + category_config["impacted_systems"]))
    rules_triggered = [f"{category}: {keyword}" for keyword in evidence_by_category[category]]

    evidence = []
    for source_name, source_values in (payload.get("signals") or {}).items():
        if source_values:
            evidence.append(
                {
                    "source": source_name,
                    "summary": ", ".join(source_values[:2]) if isinstance(source_values, list) else str(source_values),
                }
            )

    probable_root_causes = [
        {
            "cause": f"Primary evidence indicates {category}.",
            "confidence": confidence,
            "supporting_evidence": evidence_by_category[category],
        }
    ]
    if historical_matches:
        probable_root_causes.append(
            {
                "cause": f"Similar to {historical_matches[0]['incident_id']} - {historical_matches[0]['title']}.",
                "confidence": max(0.4, historical_matches[0]["similarity"]),
                "supporting_evidence": [historical_matches[0]["category"]],
            }
        )

    blast_radius = {
        "severity": "high" if confidence >= 0.8 else "medium",
        "affected_domains": impacted_systems,
        "reasoning": "Blast radius is inferred from explicit components plus category-specific platform domains.",
    }

    return {
        "issue_id": payload.get("issue_id", "unassigned"),
        "title": payload.get("title", "Untitled incident"),
        "category": category,
        "confidence_score": confidence,
        "requires_human_review": confidence < 0.55,
        "agents_invoked": _pick_agents(payload),
        "analysis_pipeline": PIPELINE_STEPS,
        "probable_root_causes": probable_root_causes,
        "impacted_systems": impacted_systems,
        "historical_matches": historical_matches,
        "blast_radius": blast_radius,
        "recommendations": {
            "remediation": category_config["remediation"],
            "prevention": category_config["prevention"],
        },
        "explainability": {
            "rules_triggered": rules_triggered,
            "correlated_signals": [item["source"] for item in evidence] or ["issue description"],
            "note": "This demonstrator intentionally uses deterministic evidence correlation to avoid unsupported claims.",
        },
        "evidence": evidence,
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok", "service": "qa-rca-agent"})

    @app.get("/api/v1/blueprint")
    def blueprint() -> Any:
        return jsonify(PLATFORM_BLUEPRINT)

    @app.post("/api/v1/rca/analyze")
    def analyze() -> Any:
        payload = request.get_json(silent=True) or {}
        if not payload:
            return jsonify({"error": "JSON payload is required"}), 400
        return jsonify(_analyze_payload(payload))

    @app.get("/")
    def index() -> Any:
        return render_template("index.html", blueprint=PLATFORM_BLUEPRINT)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
