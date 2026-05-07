import sqlite3
from datetime import datetime, timedelta, timezone
from collections import Counter
import re
from typing import List, Dict, Any, Optional, Tuple


class RCAAnalyzer:
    """
    Incremental enterprise-style analyzer using hybrid intelligence:
    - Rules (taxonomy + keyword signals)
    - Correlation (cross-signal scoring)
    - Retrieval (historical similarity from existing issue corpus)
    - Structured RCA output (confidence + evidence + recommendations)
    """

    RCA_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
        "test_automation_issue": ["playwright", "selenium", "robot", "flaky", "locator", "assertion"],
        "environment_issue": ["environment", "staging", "prod", "uat", "env", "parity"],
        "data_issue": ["data", "dataset", "seed", "migration", "null", "constraint", "integrity"],
        "api_contract_issue": ["api", "contract", "schema", "payload", "serialization", "deserialization", "400", "422"],
        "backend_logic_defect": ["backend", "logic", "exception", "business-rule", "validation", "service", "500"],
        "infrastructure_failure": ["kubernetes", "k8s", "pod", "node", "memory", "cpu", "disk", "network", "infra"],
        "authentication_issue": ["auth", "oauth", "token", "jwt", "unauthorized", "forbidden", "401", "403", "login"],
        "integration_failure": ["integration", "dependency", "third-party", "timeout", "upstream", "downstream", "webhook"],
        "deployment_regression": ["deploy", "release", "rollback", "commit", "version", "feature flag", "regression"],
        "configuration_drift": ["config", "configuration", "drift", "mismatch", "property", "secret", "toggle"],
        "performance_bottleneck": ["latency", "performance", "slow", "timeout", "p95", "p99", "throughput"],
        "dependency_outage": ["outage", "dependency", "dns", "redis", "database down", "service unavailable", "503"],
    }

    PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

    STOP_WORDS = {
        "the", "and", "for", "are", "but", "not", "with", "this", "that", "from",
        "have", "has", "had", "will", "would", "could", "should", "into", "after",
        "before", "during", "when", "where", "which", "while", "error", "issue",
        "failed", "failure", "test", "tests", "flow", "user", "users", "system",
    }

    def __init__(self, db_path: str = "qa_agent.db"):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{3,}\b", (text or "").lower())
        return [t for t in tokens if t not in self.STOP_WORDS]

    def _issue_text(self, issue_row: Tuple[Any, ...]) -> str:
        title = issue_row[1] or ""
        description = issue_row[2] or ""
        category = issue_row[5] or ""
        return f"{title} {description} {category}".strip()

    def analyze_patterns(self, days: int = 30) -> Dict[str, Any]:
        """Analyze issue patterns over time."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            SELECT id, title, description, severity, category, created_at
            FROM issues
            WHERE created_at >= ?
            ORDER BY created_at DESC
            """,
            (cutoff_str,),
        )
        issues = cursor.fetchall()
        conn.close()

        if not issues:
            return {"message": "No issues found"}

        category_counts = Counter([i[4] for i in issues if i[4]])
        severity_counts = Counter([i[3] for i in issues if i[3]])

        all_text = " ".join([f"{i[1]} {i[2] or ''}" for i in issues])
        filtered_keywords = self._tokenize(all_text)
        keyword_stats = Counter(filtered_keywords).most_common(10)

        dates = [str(i[5])[:10] for i in issues if i[5]]
        daily_trend = Counter(dates)

        most_urgent = [
            {"id": i[0], "title": i[1], "severity": i[3], "category": i[4], "created_at": i[5]}
            for i in sorted(
                [row for row in issues if (row[3] or "").lower() in {"high", "critical"}],
                key=lambda x: str(x[5]),
                reverse=True,
            )[:5]
        ]

        return {
            "period_days": days,
            "total_issues": len(issues),
            "category_distribution": dict(category_counts),
            "severity_distribution": dict(severity_counts),
            "top_keywords": [{"word": w, "count": c} for w, c in keyword_stats],
            "daily_trend": dict(daily_trend),
            "most_urgent_issues": most_urgent,
        }

    def fishbone_diagram(self, issue_id: int) -> Dict[str, List[str]]:
        """Generate Fishbone diagram categories for a specific issue."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT category, items FROM fishbone_categories
            WHERE issue_id = ?
            """,
            (issue_id,),
        )
        categories = cursor.fetchall()
        conn.close()

        return {cat[0]: cat[1].split(",") if cat[1] else [] for cat in categories}

    def five_whys_analysis(self, issue_id: int) -> List[Dict[str, Any]]:
        """Retrieve and analyze 5 Whys for an issue."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT level, question, answer FROM five_whys
            WHERE issue_id = ?
            ORDER BY level
            """,
            (issue_id,),
        )
        whys = cursor.fetchall()
        conn.close()

        return [{"level": l, "question": q, "answer": a} for l, q, a in whys]

    def recommendation_engine(self, issue_id: int) -> List[Dict[str, Any]]:
        """Generate preventive recommendations based on issue patterns."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT recommendation, priority FROM recommendations
            WHERE issue_id = ?
            """,
            (issue_id,),
        )
        recs = cursor.fetchall()
        conn.close()

        pattern_involved = self.analyze_patterns(30)
        top_keywords = pattern_involved.get("top_keywords", [])

        enhanced_recs = []
        for rec, priority in recs:
            normalized_priority = (priority or "medium").lower()
            keyword_context = [kw for kw in top_keywords if kw["word"] in (rec or "").lower()]

            if keyword_context and self.PRIORITY_ORDER.get(normalized_priority, 0) < self.PRIORITY_ORDER["high"]:
                normalized_priority = "high"

            enhanced_recs.append(
                {
                    "recommendation": rec,
                    "priority": normalized_priority,
                    "context": [kw["word"] for kw in keyword_context],
                }
            )

        return sorted(
            enhanced_recs,
            key=lambda x: self.PRIORITY_ORDER.get((x.get("priority") or "low").lower(), 0),
            reverse=True,
        )

    def _get_issue(self, issue_id: int) -> Optional[Tuple[Any, ...]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, severity, status, category, created_at, updated_at
            FROM issues WHERE id = ?
            """,
            (issue_id,),
        )
        issue = cursor.fetchone()
        conn.close()
        return issue

    def _extract_signals(self, issue_row: Tuple[Any, ...]) -> Dict[str, Any]:
        text = self._issue_text(issue_row).lower()
        tokens = self._tokenize(text)
        token_counts = Counter(tokens)

        severity = (issue_row[3] or "medium").lower()
        category = (issue_row[5] or "").lower()

        category_scores = {}
        for rca_category, words in self.RCA_CATEGORY_KEYWORDS.items():
            score = 0
            for w in words:
                if w in text:
                    score += 1
            if category and category in rca_category:
                score += 2
            if score > 0:
                category_scores[rca_category] = score

        ordered_categories = sorted(category_scores.items(), key=lambda kv: kv[1], reverse=True)
        predicted_category = ordered_categories[0][0] if ordered_categories else "backend_logic_defect"

        impacted_components = self._detect_impacted_components(text, tokens)
        error_codes = sorted(set(re.findall(r"\b(?:4\d\d|5\d\d)\b", text)))
        stack_trace_hint = bool(re.search(r"(traceback|exception|stack trace|nullpointer|segmentation fault)", text))

        return {
            "severity": severity,
            "source_category": category or "general",
            "keywords": [kw for kw, _ in token_counts.most_common(12)],
            "predicted_category": predicted_category,
            "category_rankings": [{"category": c, "score": s} for c, s in ordered_categories[:5]],
            "impacted_components": impacted_components,
            "error_codes": error_codes,
            "stack_trace_detected": stack_trace_hint,
        }

    def _detect_impacted_components(self, text: str, tokens: List[str]) -> List[str]:
        components = set()
        service_tokens = re.findall(r"\b([a-z0-9_-]+(?:-service|-api|-worker|-db|-gateway))\b", text)
        for token in service_tokens:
            components.add(token)

        for token in tokens:
            if token in {"checkout", "payment", "auth", "search", "catalog", "order", "inventory"}:
                components.add(f"{token}-service")

        if "kubernetes" in text or "k8s" in text:
            components.add("kubernetes-cluster")
        if "database" in text or "db" in tokens:
            components.add("primary-database")

        return sorted(components)

    def _historical_similarity(self, issue_row: Tuple[Any, ...], limit: int = 5) -> List[Dict[str, Any]]:
        current_id = issue_row[0]
        current_tokens = set(self._tokenize(self._issue_text(issue_row)))
        current_category = (issue_row[5] or "").lower()

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, severity, status, category, created_at, updated_at
            FROM issues
            WHERE id != ?
            ORDER BY created_at DESC
            LIMIT 200
            """,
            (current_id,),
        )
        candidates = cursor.fetchall()
        conn.close()

        results = []
        for row in candidates:
            tokens = set(self._tokenize(self._issue_text(row)))
            if not tokens and not current_tokens:
                similarity = 0.0
            else:
                similarity = len(current_tokens & tokens) / float(len(current_tokens | tokens) or 1)

            if current_category and (row[5] or "").lower() == current_category:
                similarity += 0.15

            if similarity >= 0.15:
                results.append(
                    {
                        "issue_id": row[0],
                        "title": row[1],
                        "category": row[5] or "general",
                        "severity": row[3] or "medium",
                        "similarity": round(min(similarity, 1.0), 3),
                    }
                )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def _build_rule_based_hypotheses(self, signals: Dict[str, Any]) -> List[Dict[str, Any]]:
        hypotheses = []
        category = signals["predicted_category"]
        impacted = signals.get("impacted_components", [])
        severity = signals.get("severity", "medium")

        base_score = 0.55
        if severity in {"high", "critical"}:
            base_score += 0.1
        if signals.get("error_codes"):
            base_score += 0.05
        if signals.get("stack_trace_detected"):
            base_score += 0.05
        if len(impacted) > 1:
            base_score += 0.05

        summary_map = {
            "test_automation_issue": "Test automation instability caused by fragile selectors or flaky timing assumptions.",
            "environment_issue": "Environment inconsistency caused divergent runtime behavior across test and execution stages.",
            "data_issue": "Data quality or schema assumptions failed for critical execution paths.",
            "api_contract_issue": "API contract mismatch between producer and consumer payload/schema expectations.",
            "backend_logic_defect": "Backend business logic/validation defect introduced invalid execution outcomes.",
            "infrastructure_failure": "Infrastructure instability (resource/network/platform) caused service disruption.",
            "authentication_issue": "Authentication or token-validation flow failure blocked authorized access.",
            "integration_failure": "External/internal dependency integration failure propagated request-level errors.",
            "deployment_regression": "Recent deployment introduced regression due to code/config/version change.",
            "configuration_drift": "Configuration drift/mismatch created behavior deviations across environments.",
            "performance_bottleneck": "Performance degradation from resource contention or inefficient execution path.",
            "dependency_outage": "Critical dependency outage/unavailability caused cascading failures.",
        }

        primary = {
            "hypothesis_id": "H1",
            "category": category,
            "summary": summary_map.get(category, summary_map["backend_logic_defect"]),
            "score": round(min(base_score, 0.95), 3),
            "impacted_components": impacted,
            "evidence_refs": ["E1", "E2"],
        }
        hypotheses.append(primary)

        ranked = signals.get("category_rankings", [])
        if len(ranked) > 1:
            secondary_category = ranked[1]["category"]
            hypotheses.append(
                {
                    "hypothesis_id": "H2",
                    "category": secondary_category,
                    "summary": summary_map.get(secondary_category, "Secondary correlated hypothesis from signal overlap."),
                    "score": round(max(primary["score"] - 0.18, 0.35), 3),
                    "impacted_components": impacted[:2],
                    "evidence_refs": ["E1"],
                }
            )

        return hypotheses

    def _confidence_score(
        self,
        signals: Dict[str, Any],
        hypotheses: List[Dict[str, Any]],
        similar_cases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        data_quality = 0.5 + min(len(signals.get("keywords", [])) / 20.0, 0.3)
        if signals.get("error_codes"):
            data_quality += 0.05
        if signals.get("stack_trace_detected"):
            data_quality += 0.05
        data_quality = min(data_quality, 1.0)

        rule_match = min((hypotheses[0]["score"] if hypotheses else 0.4), 1.0)
        historical = min((similar_cases[0]["similarity"] if similar_cases else 0.0), 1.0)

        agreement = 0.55
        if len(signals.get("category_rankings", [])) > 0:
            top = signals["category_rankings"][0]["score"]
            second = signals["category_rankings"][1]["score"] if len(signals["category_rankings"]) > 1 else 0
            gap = top - second
            agreement += min(gap * 0.05, 0.2)
        agreement = min(agreement, 1.0)

        score = (
            0.30 * rule_match
            + 0.25 * agreement
            + 0.20 * historical
            + 0.25 * data_quality
        )

        level = "high" if score >= 0.8 else "medium" if score >= 0.6 else "low"

        return {
            "score": round(score, 3),
            "level": level,
            "factors": {
                "score": round(score, 3),
                "rule_match_strength": round(rule_match, 3),
                "cross_signal_agreement": round(agreement, 3),
                "historical_similarity": round(historical, 3),
                "data_quality": round(data_quality, 3),
            },
        }

    def _recommendations(self, signals: Dict[str, Any], category: str) -> Dict[str, List[str]]:
        keywords = signals.get("keywords", [])
        key_signal = keywords[0] if keywords else "critical-path"

        immediate = [
            f"Contain incident impact by validating and isolating failures around '{key_signal}'.",
            "Run targeted verification on impacted components and apply rollback if regression is confirmed.",
        ]
        preventive = [
            "Add risk-based regression scenarios for this failure class into CI quality gates.",
            "Introduce structured observability checkpoints (logs/metrics/traces) for earlier anomaly detection.",
        ]

        category_specific = {
            "api_contract_issue": "Add contract tests and schema compatibility checks between producer/consumer APIs.",
            "deployment_regression": "Enforce canary + automated rollback policy using release health indicators.",
            "test_automation_issue": "Stabilize test selectors and quarantine flaky scenarios with retry diagnostics.",
            "infrastructure_failure": "Implement proactive infrastructure SLO alerting and capacity guardrails.",
            "authentication_issue": "Add token lifecycle and auth policy validation tests for all login/session paths.",
        }
        if category in category_specific:
            preventive.insert(0, category_specific[category])

        return {"immediate": immediate, "preventive": preventive}

    def generate_rca_report(self, issue_id: int) -> Dict[str, Any]:
        issue = self._get_issue(issue_id)
        if not issue:
            return {"error": f"Issue {issue_id} not found"}

        signals = self._extract_signals(issue)
        similar_cases = self._historical_similarity(issue, limit=5)
        hypotheses = self._build_rule_based_hypotheses(signals)
        confidence = self._confidence_score(signals, hypotheses, similar_cases)

        primary_hypothesis = hypotheses[0] if hypotheses else {}
        predicted_category = primary_hypothesis.get("category", "backend_logic_defect")
        impacted_components = signals.get("impacted_components", [])

        evidence = [
            {
                "evidence_id": "E1",
                "source": "issue_record",
                "signal": f"Severity={signals.get('severity')}, SourceCategory={signals.get('source_category')}",
            },
            {
                "evidence_id": "E2",
                "source": "keyword_analysis",
                "signal": f"Top keywords: {', '.join(signals.get('keywords', [])[:5]) or 'none'}",
            },
        ]
        if similar_cases:
            evidence.append(
                {
                    "evidence_id": "E3",
                    "source": "historical_similarity",
                    "signal": f"Most similar issue #{similar_cases[0]['issue_id']} (similarity={similar_cases[0]['similarity']})",
                }
            )

        recommendations = self._recommendations(signals, predicted_category)

        return {
            "incident_id": issue[0],
            "title": issue[1],
            "status": issue[4] or "open",
            "category": predicted_category,
            "root_cause": {
                "summary": primary_hypothesis.get("summary", "Insufficient evidence"),
                "type": predicted_category,
                "component": impacted_components[0] if impacted_components else "unknown-component",
                "environment": "unknown",
            },
            "confidence": confidence,
            "hypotheses": hypotheses,
            "impacted_scope": {
                "components": impacted_components,
                "systems": [signals.get("source_category", "general")],
            },
            "evidence": evidence,
            "historical_matches": similar_cases,
            "recommendations": recommendations,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
