from flask import Flask, render_template, request, redirect, url_for, jsonify
import re

try:
    from . import models as models_module
    from .models import Issue, RootCause, FiveWhys, FishboneCategory, Recommendation, init_db
    from .analyzer import RCAAnalyzer
except ImportError:
    import models as models_module
    from models import Issue, RootCause, FiveWhys, FishboneCategory, Recommendation, init_db
    from analyzer import RCAAnalyzer

app = Flask(__name__)

STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "with", "this", "that", "from", "have",
    "has", "had", "will", "would", "could", "should", "into", "after", "before", "during",
    "when", "where", "which", "while", "error", "issue", "failed", "failure", "test", "tests"
}

MIN_ALNUM_KEYWORD_CHARS = 3


def _clean_text(value):
    return (value or "").strip()


def _extract_issue_keywords(issue, max_items=5):
    text = f"{_clean_text(issue.title)} {_clean_text(issue.description)}".lower()
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text)

    keywords = []
    seen = set()
    for token in tokens:
        if sum(1 for char in token if char.isalnum()) < MIN_ALNUM_KEYWORD_CHARS:
            continue
        if token in STOP_WORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= max_items:
            break

    if not keywords and issue.category:
        keywords.append(issue.category.lower())
    return keywords


def _context_label(issue):
    category = _clean_text(issue.category) or "workflow"
    return category.lower()


def _issue_summary(issue, limit=160):
    description = _clean_text(issue.description)
    if description:
        summary = re.split(r"[.!?]\s+", description)[0].strip()
        if len(summary) > limit:
            summary = f"{summary[:limit].rstrip()}..."
        return summary
    title = _clean_text(issue.title)
    return title if len(title) <= limit else f"{title[:limit].rstrip()}..."


def _failure_mode_hypothesis(issue):
    category = _context_label(issue)

    category_map = {
        "backend": (
            "request handling or business-rule validation did not guard this scenario",
            "runtime monitoring did not flag the anomaly before user impact",
            "release checks focused on happy-path behavior over exception paths",
        ),
        "server": (
            "service dependency or deployment-state drift introduced unstable behavior",
            "health and error-rate alerts were not tuned for this failure signature",
            "operational readiness checks did not enforce rollback-safe criteria",
        ),
        "api": (
            "input contract assumptions diverged between producer and consumer paths",
            "API contract monitoring did not capture this mismatch early enough",
            "versioning and backward-compatibility checks were not strict for this path",
        ),
        "database": (
            "data constraints or migration assumptions were violated in production flow",
            "data-quality checks did not catch the drift in time",
            "schema-change validation lacked realistic production-like data sets",
        ),
        "ui": (
            "client-side state or interaction flow allowed an invalid transition",
            "UI telemetry lacked actionable signal for this sequence",
            "pre-release scenario testing did not include this user journey depth",
        ),
        "frontend": (
            "client-side state or interaction flow allowed an invalid transition",
            "UI telemetry lacked actionable signal for this sequence",
            "pre-release scenario testing did not include this user journey depth",
        ),
        "qa": (
            "validation strategy did not cover this edge path with enough depth",
            "quality gates did not surface the risk signal before release",
            "risk-based test selection missed this failure-prone variation",
        ),
        "process": (
            "the documented process had ambiguity at a critical decision step",
            "handoff checkpoints did not detect drift from expected behavior",
            "process governance did not enforce closed-loop learning on similar incidents",
        ),
    }

    for key, mapped in category_map.items():
        if key in category:
            return mapped

    return (
        "a workflow gap allowed an unhandled scenario to pass through controls",
        "monitoring and validation signals were not specific enough for early detection",
        "ownership and review controls were not explicit for this type of risk",
    )


def _seed_five_whys(issue):
    issue_context = _issue_summary(issue)
    category = _context_label(issue)
    keywords = _extract_issue_keywords(issue, max_items=3)
    primary_signal = keywords[0] if keywords else "this condition"
    secondary_signal = keywords[1] if len(keywords) > 1 else "related edge-cases"

    immediate_cause, detection_gap, systemic_gap = _failure_mode_hypothesis(issue)

    whys = [
        (
            f"Why did '{issue_context}' happen in the {category} flow?",
            f"The {category} flow likely failed around {primary_signal}, where {immediate_cause}."
        ),
        (
            f"Why was the {primary_signal} failure not caught before it reached users?",
            f"Detection controls for {primary_signal} were insufficient; {detection_gap}."
        ),
        (
            "Why were detection controls for this scenario insufficient?",
            f"Existing checks prioritized common paths, while {secondary_signal} scenarios were under-tested."
        ),
        (
            "Why did testing and review underweight this risk pattern?",
            f"The release process lacked explicit risk weighting for this failure type; {systemic_gap}."
        ),
        (
            "Why did this gap persist across cycles?",
            "Accountability for scenario-specific prevention was not concretely assigned, so the learning loop stayed weak."
        ),
    ]

    for level, (question, answer) in enumerate(whys, start=1):
        FiveWhys(issue_id=issue.id, level=level, question=question, answer=answer).save()


def _seed_fishbone(issue):
    category = _context_label(issue)
    title = _clean_text(issue.title) or "this issue"
    summary = _issue_summary(issue)
    keywords = _extract_issue_keywords(issue, max_items=4)

    token_1 = keywords[0] if keywords else "critical path"
    token_2 = keywords[1] if len(keywords) > 1 else "edge-case flow"

    fishbone_map = {
        "people": [
            f"Unclear ownership for triaging {category} incidents tied to {token_1}",
            f"Knowledge gap on handling {token_2} in runbooks",
            f"Handoff assumptions between QA and engineering for '{title}'"
        ],
        "process": [
            f"No mandatory checklist targeting '{summary}' before release",
            f"Regression criteria did not explicitly include {token_1} failure patterns",
            f"Post-change validation gates were shallow for {category} variations"
        ],
        "tools": [
            f"Monitoring lacked alert rules for {token_1} anomalies",
            f"Automation coverage was weak for {token_2} scenarios",
            "Logs/telemetry did not expose root-cause signals with enough precision"
        ],
        "environment": [
            f"{category.title()} behavior not consistently validated across environments",
            "Configuration/dependency drift risk not checked as a release gate",
            "Environment parity checks were reactive instead of preventive"
        ],
    }

    for cat, item_list in fishbone_map.items():
        FishboneCategory(issue_id=issue.id, category=cat, items=", ".join(item_list)).save()


def _seed_recommendations(issue):
    severity = (_clean_text(issue.severity) or "medium").lower()
    category = _context_label(issue)
    keywords = _extract_issue_keywords(issue, max_items=2)

    primary_signal = keywords[0] if keywords else "critical flow"
    secondary_signal = keywords[1] if len(keywords) > 1 else "edge-case scenarios"

    high_priority = "high" if severity in {"high", "critical"} else "medium"

    recs = [
        (f"Add preventive validation checks around {primary_signal} in the {category} workflow.", high_priority),
        (f"Create regression scenarios for {secondary_signal} and enforce them as release criteria.", "high"),
        ("Introduce targeted monitoring alerts with clear ownership for triage and closure.", "medium"),
    ]

    for recommendation, priority in recs:
        Recommendation(issue_id=issue.id, recommendation=recommendation, priority=priority).save()


def _build_impact_assessment(issue):
    severity = (_clean_text(issue.severity) or "medium").lower()
    category = _context_label(issue)
    summary = _issue_summary(issue)
    keywords = _extract_issue_keywords(issue, max_items=3)

    signal = keywords[0] if keywords else "the impacted path"

    severity_to_business = {
        "critical": "High risk of immediate business disruption, SLA breach, or revenue-impacting outage.",
        "high": "Significant risk to customer trust and delivery commitments if recurrence is not controlled.",
        "medium": "Moderate delivery and quality risk that can compound over repeated occurrences.",
        "low": "Localized impact with limited business disruption, but still useful for preventive hardening.",
    }

    severity_to_user = {
        "critical": f"Users can face blocking failures while executing {signal}-related flows.",
        "high": f"Users may see frequent degradation or inconsistent behavior around {signal}.",
        "medium": f"A subset of users may experience intermittent issues in {signal}-dependent paths.",
        "low": f"User friction is likely limited and situational in {signal} scenarios.",
    }

    severity_to_operational = {
        "critical": "Incident response overhead is high and requires rapid cross-team coordination.",
        "high": "Support and engineering workload increases due to escalations and rework.",
        "medium": "Teams absorb additional triage/retest effort that impacts planned work.",
        "low": "Operational overhead is manageable but indicates process improvement opportunities.",
    }

    likelihood = "High likelihood of recurrence until targeted controls are implemented." if severity in {"high", "critical"} else "Moderate likelihood of recurrence without focused preventive actions."
    blast_radius = f"Primary blast radius centers on {category} workflows related to: {summary}."

    return {
        "business": severity_to_business.get(severity, severity_to_business["medium"]),
        "user": severity_to_user.get(severity, severity_to_user["medium"]),
        "operational": severity_to_operational.get(severity, severity_to_operational["medium"]),
        "likelihood": likelihood,
        "blast_radius": blast_radius,
    }


@app.route('/')
def index():
    issues = Issue.get_all()
    return render_template('index.html', issues=issues)


@app.route('/issues/create', methods=['POST'])
def create_issue():
    title = request.form['title']
    description = request.form['description']
    severity = request.form.get('severity', 'medium')
    category = request.form.get('category', 'general')

    issue = Issue(title=title, description=description, severity=severity, category=category)
    issue.save()

    return redirect(url_for('index'))


@app.route('/analysis/<int:issue_id>')
def analyze_issue(issue_id):
    issue = Issue.get_by_id(issue_id)
    root_causes = RootCause.get_by_issue(issue_id)
    five_whys = FiveWhys.get_by_issue(issue_id)
    fishbone_categories = FishboneCategory.get_by_issue(issue_id)
    recommendations = Recommendation.get_by_issue(issue_id)

    if issue and not five_whys:
        _seed_five_whys(issue)
        five_whys = FiveWhys.get_by_issue(issue_id)

    if issue and not fishbone_categories:
        _seed_fishbone(issue)
        fishbone_categories = FishboneCategory.get_by_issue(issue_id)

    if issue and not recommendations:
        _seed_recommendations(issue)
        recommendations = Recommendation.get_by_issue(issue_id)

    # Convert fishbone_categories list to dict for template
    fishbone_dict = {}
    for fc in fishbone_categories:
        if fc.items:
            item_list = [item.strip() for item in fc.items.split(',')]
        else:
            item_list = []
        fishbone_dict[fc.category] = item_list

    impact_assessment = _build_impact_assessment(issue) if issue else {}

    return render_template(
        'analysis.html',
        issue=issue,
        root_causes=root_causes,
        five_whys=five_whys,
        fishbone_categories=fishbone_dict,
        recommendations=recommendations,
        impact_assessment=impact_assessment
    )


@app.route('/api/analyze_5whys/<int:issue_id>', methods=['POST'])
def api_analyze_5whys(issue_id):
    """API endpoint to trigger 5 Whys analysis"""
    data = request.get_json()
    level = data.get('level', 1)
    question = data.get('question', f'Why #{level}')

    # Simple simulation - in real implementation this would analyze deeper
    five_why = FiveWhys(issue_id=issue_id, level=level, question=question)
    five_why.save()

    return jsonify({'status': 'success', 'message': '5 Whys analysis added'})


@app.route('/api/add_cause/<int:issue_id>', methods=['POST'])
def api_add_cause(issue_id):
    """API endpoint to add a root cause"""
    data = request.get_json()
    cause = data.get('cause', '')
    category = data.get('category', '')
    evidence = data.get('evidence', '')

    root_cause = RootCause(
        issue_id=issue_id,
        cause=cause,
        category=category,
        evidence=evidence
    )
    root_cause.save()

    return jsonify({'status': 'success', 'message': 'Root cause added'})


@app.route('/api/add_recommendation/<int:issue_id>', methods=['POST'])
def api_add_recommendation(issue_id):
    """API endpoint to add a recommendation"""
    data = request.get_json()
    recommendation = data.get('recommendation', '')
    priority = data.get('priority', 'medium')

    rec = Recommendation(
        issue_id=issue_id,
        recommendation=recommendation,
        priority=priority
    )
    rec.save()

    return jsonify({'status': 'success', 'message': 'Recommendation added'})


@app.route('/api/rca_report/<int:issue_id>', methods=['GET'])
def api_rca_report(issue_id):
    """API endpoint to generate structured RCA report with confidence and evidence."""
    analyzer = RCAAnalyzer(models_module.DATABASE)
    report = analyzer.generate_rca_report(issue_id)

    if report.get("error"):
        return jsonify({"status": "error", "message": report["error"]}), 404

    return jsonify({"status": "success", "report": report})


if __name__ == '__main__':
    init_db()
    app.run(debug=False, port=5000)
