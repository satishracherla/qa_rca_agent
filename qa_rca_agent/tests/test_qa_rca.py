import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qa_rca_agent.models as models
import qa_rca_agent.app as app_module
from qa_rca_agent.analyzer import RCAAnalyzer


class TestQA_RCA(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_qa.db"

        # Override the database path for testing
        self.original_db = models.DATABASE
        models.DATABASE = self.db_path

        # Initialize the database schema
        models.init_db()
        self.analyzer = RCAAnalyzer(self.db_path)

        # Flask test client
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def test_create_issue(self):
        issue = models.Issue(
            title="Test Issue",
            description="This is a test issue for RCA purposes.",
            severity="high",
            category="server",
        )
        issue.save()
        self.assertIsNotNone(issue.id)

    def test_analysis_patterns(self):
        issue = models.Issue(title="Pattern Test", severity="medium")
        issue.save()
        pattern = self.analyzer.analyze_patterns(days=7)
        self.assertIn("total_issues", pattern)

    def test_fishbone_diagram(self):
        issue = models.Issue(title="Fishbone Test", category="hardware", severity="high")
        issue.save()
        result = self.analyzer.fishbone_diagram(issue.id)
        self.assertIsInstance(result, dict)

    def test_five_whys_analysis(self):
        issue = models.Issue(title="Five Whys Test", severity="critical")
        issue.save()
        result = self.analyzer.five_whys_analysis(issue.id)
        self.assertIsInstance(result, list)

    def test_recommendation_engine(self):
        issue = models.Issue(title="Recommendation Test", severity="high")
        issue.save()
        result = self.analyzer.recommendation_engine(issue.id)
        self.assertIsInstance(result, list)

    def test_analysis_seeding_is_issue_specific(self):
        issue = models.Issue(
            title="Checkout payment API timeout",
            description="Customer payment requests time out during checkout when promo codes are applied.",
            severity="high",
            category="api",
        )
        issue.save()

        # Trigger automatic seeding
        response = self.client.get(f"/analysis/{issue.id}")
        self.assertEqual(response.status_code, 200)

        five_whys = models.FiveWhys.get_by_issue(issue.id)
        self.assertEqual(len(five_whys), 5)

        why_text = " ".join([f"{w.question} {w.answer}".lower() for w in five_whys])
        self.assertTrue("payment" in why_text or "checkout" in why_text)

        fishbone = models.FishboneCategory.get_by_issue(issue.id)
        self.assertGreaterEqual(len(fishbone), 4)

        fishbone_text = " ".join([(f.items or "").lower() for f in fishbone])
        self.assertTrue("payment" in fishbone_text or "checkout" in fishbone_text or "timeout" in fishbone_text)

    def test_impact_assessment_renders_contextual_content(self):
        issue = models.Issue(
            title="Search indexing lag",
            description="Catalog updates appear in search after several hours, affecting product discoverability.",
            severity="critical",
            category="backend",
        )
        issue.save()

        response = self.client.get(f"/analysis/{issue.id}")
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True).lower()
        self.assertIn("impact assessment", html)
        self.assertIn("business impact", html)
        self.assertIn("blast radius", html)
        self.assertIn("backend workflows", html)
        self.assertTrue("search" in html or "indexing" in html)

    def test_generate_rca_report_structured_output(self):
        baseline = models.Issue(
            title="Checkout API timeout from gateway",
            description="Payment API timeout observed in checkout-service after deployment.",
            severity="high",
            category="api",
        )
        baseline.save()

        target = models.Issue(
            title="Authentication token validation failure",
            description="Users receive 401 unauthorized due to JWT token parsing issue in auth-service.",
            severity="critical",
            category="api",
        )
        target.save()

        report = self.analyzer.generate_rca_report(target.id)

        self.assertEqual(report["incident_id"], target.id)
        self.assertIn("category", report)
        self.assertIn("root_cause", report)
        self.assertIn("confidence", report)
        self.assertIn("evidence", report)
        self.assertIn("historical_matches", report)
        self.assertIn("recommendations", report)
        self.assertGreaterEqual(report["confidence"]["score"], 0.0)
        self.assertLessEqual(report["confidence"]["score"], 1.0)
        self.assertIn("score", report["confidence"]["factors"])
        self.assertTrue(isinstance(report["hypotheses"], list) and len(report["hypotheses"]) >= 1)

    def test_api_rca_report_endpoint(self):
        issue = models.Issue(
            title="Deployment caused API 500 spike",
            description="After release, checkout-api returns 500 with stack trace in backend logs.",
            severity="high",
            category="server",
        )
        issue.save()

        response = self.client.get(f"/api/rca_report/{issue.id}")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertEqual(payload["status"], "success")
        self.assertIn("report", payload)
        self.assertEqual(payload["report"]["incident_id"], issue.id)
        self.assertIn("confidence", payload["report"])
        self.assertIn("hypotheses", payload["report"])

    def tearDown(self):
        # Restore original database path
        models.DATABASE = self.original_db
        if os.path.exists(self.db_path):
            os.remove(self.db_path)


if __name__ == "__main__":
    unittest.main()
