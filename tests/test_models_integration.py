"""Real-model integration test. Skipped unless ASKFHIR_INTEGRATION=1
(models are downloaded on first use)."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("ASKFHIR_INTEGRATION") != "1",
    reason="set ASKFHIR_INTEGRATION=1 to run real-model tests",
)


def test_real_pipeline_end_to_end():
    from askfhir.service import AskFHIRService

    svc = AskFHIRService.load(fake=False)
    result = svc.ask("What does the rank mean in an Encounter diagnosis?")
    assert result["abstained"] is False
    assert any(s["doc_id"] == "encounter-resource" for s in result["sources"][:3])
    off_topic = svc.ask("What is the capital of France?")
    assert off_topic["abstained"] is True
