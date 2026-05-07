import unittest

from app import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.client = self.app.test_client()

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_blueprint_endpoint_exposes_architecture_sections(self) -> None:
        response = self.client.get("/api/v1/blueprint")
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("improved_architecture", data)
        self.assertGreaterEqual(len(data["multi_agent_design"]), 7)
        self.assertIn("confidence_scoring_strategy", data)
        self.assertIn("security_recommendations", data)

    def test_rca_analysis_returns_structured_deployment_regression(self) -> None:
        response = self.client.post(
            "/api/v1/rca/analyze",
            json={
                "issue_id": "BUG-101",
                "title": "Checkout tests started failing after release",
                "description": "Feature flag change triggered regression after deployment",
                "components": ["checkout-service"],
                "signals": {
                    "test_results": ["Playwright checkout suite failing after release"],
                    "deployment_changes": ["payment-service deployment introduced feature flag checkout_v2"],
                    "logs": ["HTTP 500 errors observed after deployment"],
                    "ci_metadata": ["Regression started in the first pipeline after rollout"],
                },
            },
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["category"], "deployment regression")
        self.assertGreaterEqual(data["confidence_score"], 0.6)
        self.assertIn("checkout-service", data["impacted_systems"])
        self.assertIn("Deployment Analysis Agent", data["agents_invoked"])
        self.assertIn("recommendations", data)


if __name__ == "__main__":
    unittest.main()
