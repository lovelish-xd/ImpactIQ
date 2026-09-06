import json
import unittest
from unittest.mock import MagicMock, patch

from src.ai import AIExplanation, build_explanation_prompt, explain_analysis


class AIExplanationTests(unittest.TestCase):
    """Tests for the AI explanation layer."""

    def setUp(self):
        self.sample_analysis = {
            "analysis": {
                "title": "Impact analysis: 2 modified asset(s)",
                "baseCommit": "02ccdc8",
                "targetCommit": "5d26f89",
                "summary": {
                    "headline": "Impact analysis: 2 modified asset(s)",
                    "items": [
                        "Field customerEmail added to SaveOrderDB",
                        "New mapping added in SaveOrder",
                    ],
                },
                "affectedAssets": [
                    {
                        "name": "OrderProcessing.orderProcessing.adapters:SaveOrderDB",
                        "type": "Adapter Service",
                        "changeType": "Changed",
                        "risk": "Medium",
                    },
                    {
                        "name": "OrderProcessing.orderProcessing.services:SaveOrder",
                        "type": "Flow Service",
                        "changeType": "Changed",
                        "risk": "Medium",
                    },
                ],
                "risk": {
                    "score": 45,
                    "level": "Medium",
                    "drivers": ["2 asset(s) modified", "1 field(s) added"],
                },
                "changes": [
                    {
                        "type": "FIELD_ADDED",
                        "asset": "SaveOrderDB",
                        "description": "Field customerEmail added",
                    }
                ],
                "regressionTests": [
                    {
                        "name": "Verify SaveOrderDB accepts customerEmail",
                        "priority": "High",
                        "scenario": "Invoke SaveOrderDB with customerEmail",
                    }
                ],
                "dependencies": {
                    "edges": [{"from": "SaveOrder", "to": "SaveOrderDB", "label": "invokes"}]
                },
            }
        }

    def test_prompt_contains_constraints_and_facts(self):
        prompt = build_explanation_prompt(self.sample_analysis)
        self.assertIn("STRICT CONSTRAINTS", prompt)
        self.assertIn("Do NOT invent changes", prompt)
        self.assertIn("Do NOT alter or calculate new risk scores", prompt)
        self.assertIn("SaveOrderDB", prompt)
        self.assertIn("customerEmail", prompt)
        self.assertIn("45", prompt)

    def test_unconfigured_ai_returns_graceful_unavailable(self):
        with patch.dict("os.environ", {}, clear=True):
            result = explain_analysis(self.sample_analysis, load_env=False)
            self.assertFalse(result.available)
            self.assertEqual(result.provider, "none")
            self.assertIn("not configured", result.reason.lower())
            self.assertTrue(result.message)

    def test_successful_gemini_call(self):
        mock_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "summary": "The change adds customer email persistence to the order flow.",
                                    "sections": {
                                        "What Changed": "SaveOrderDB received a customerEmail input and SQL column.",
                                        "Impact Path": "SaveOrder and OrderProcessing invoke the modified service.",
                                        "Risk Analysis": "Medium risk due to schema and mapping changes.",
                                        "Testing Rationale": "Verify data persistence with new email field.",
                                    },
                                })
                            }
                        ]
                    }
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = explain_analysis(self.sample_analysis, api_key="dummy-gemini-key", provider="gemini")
            self.assertTrue(result.available)
            self.assertEqual(result.provider, "Google Gemini")
            self.assertIn("customer email", result.summary)
            self.assertIn("What Changed", result.sections)
            self.assertIn("Testing Rationale", result.sections)

    def test_successful_openai_call(self):
        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "summary": "Executive summary from OpenAI.",
                            "sections": {
                                "What Changed": "Field and SQL changes in SaveOrderDB.",
                            },
                        })
                    }
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = explain_analysis(self.sample_analysis, api_key="dummy-openai-key", provider="openai")
            self.assertTrue(result.available)
            self.assertEqual(result.provider, "OpenAI")
            self.assertEqual(result.summary, "Executive summary from OpenAI.")

    def test_malformed_ai_json_handled_gracefully(self):
        mock_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Not valid JSON at all!"}]
                    }
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = explain_analysis(self.sample_analysis, api_key="dummy-key", provider="gemini")
            self.assertFalse(result.available)
            self.assertIn("Malformed", result.reason)

    def test_network_error_handled_gracefully(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            result = explain_analysis(self.sample_analysis, api_key="dummy-key", provider="gemini")
            self.assertFalse(result.available)
            self.assertIn("unreachable", result.reason.lower())


if __name__ == "__main__":
    unittest.main()
