import os
import json
import pytest
from unittest.mock import patch, MagicMock

from reconcile_soa_llm import reconcile_soa

# --- Test Setup ---
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'test_outputs')

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Create test directories before tests run, and clean up after."""
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    yield
    # No cleanup needed for now, but could add `shutil.rmtree` here if needed

# --- Test Cases ---

@pytest.mark.xfail(reason="reconcile_soa now expects both text and vision inputs; vision-only passthrough is no longer supported.")
def test_vision_only_passthrough():
    """Legacy test: previously allowed vision-only passthrough (no text SoA)."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'vision_only_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'vision_only_output.json')

    vision_data = {"study": {"studyId": "VISION-123"}}
    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=None)

    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)
    assert output_data == vision_data

@pytest.mark.xfail(reason="reconcile_soa now fails fast on invalid text JSON instead of silently passing through vision-only.")
def test_invalid_text_soa_passthrough():
    """Legacy test: previously passed through vision when text JSON was invalid."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'invalid_text_vision_input.json')
    text_input_path = os.path.join(TEST_DATA_DIR, 'invalid_text_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'invalid_text_output.json')

    vision_data = {"study": {"studyId": "VISION-456"}}
    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)
    
    # Create an invalid JSON file
    with open(text_input_path, 'w') as f:
        f.write('{"this is not valid json,')

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=text_input_path)

    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)
    assert output_data == vision_data

@patch('reconcile_soa_llm.client.chat.completions.create')
def test_successful_reconciliation(mock_create):
    """Tests a successful reconciliation call to the LLM."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'reconcile_vision_input.json')
    text_input_path = os.path.join(TEST_DATA_DIR, 'reconcile_text_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'reconcile_output.json')

    vision_data = {"study": {"studyId": "VISION-789"}}
    text_data = {"study": {"studyId": "TEXT-789"}}
    reconciled_data = {"study": {"studyId": "RECONCILED-789"}}

    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)
    with open(text_input_path, 'w') as f:
        json.dump(text_data, f)

    # Mock the OpenAI API response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(reconciled_data)
    mock_create.return_value = mock_response

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=text_input_path, model_name='o3')

    # We still expect a single LLM call, but the reconciled JSON is now
    # post-processed (wrapper fields, normalization, union-subset pruning),
    # so it will not be byte-for-byte equal to reconciled_data.
    mock_create.assert_called_once()
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)

    # Basic structural sanity checks on the reconciled output. The
    # reconciler may further post-process the JSON (wrapper fields,
    # normalization, union-subset pruning), so we only assert that a
    # study object is present.
    assert isinstance(output_data, dict)
    assert 'study' in output_data

@pytest.mark.xfail(reason="reconcile_soa no longer performs an internal OpenAI model-name fallback when the primary model fails.")
@patch('reconcile_soa_llm.client.chat.completions.create')
def test_llm_failure_and_fallback(mock_create):
    """Legacy test: previously verified OpenAI model-name fallback behavior."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'fallback_vision_input.json')
    text_input_path = os.path.join(TEST_DATA_DIR, 'fallback_text_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'fallback_output.json')

    vision_data = {"study": {"studyId": "VISION-FB"}}
    text_data = {"study": {"studyId": "TEXT-FB"}}
    fallback_data = {"study": {"studyId": "FALLBACK-FB"}}

    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)
    with open(text_input_path, 'w') as f:
        json.dump(text_data, f)

    # Mock the OpenAI API to fail on the first call, succeed on the second
    mock_fallback_response = MagicMock()
    mock_fallback_response.choices[0].message.content = json.dumps(fallback_data)
    mock_create.side_effect = [
        Exception("Primary model failed"),
        mock_fallback_response
    ]

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=text_input_path, model_name='o3')

    # Primary model attempt + single fallback call
    assert mock_create.call_count == 2
    # Check that the first call was with 'o3' and the second with 'gpt-4o'
    assert mock_create.call_args_list[0].kwargs['model'] == 'o3'
    assert mock_create.call_args_list[1].kwargs['model'] == 'gpt-4o'

    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)

    # The reconciler now post-processes the JSON, so we only enforce
    # high-level structural expectations rather than exact equality.
    assert isinstance(output_data, dict)
    assert 'study' in output_data


@patch('reconcile_soa_llm.client.chat.completions.create')
def test_union_subset_and_schedule_timeline_postprocessing(mock_create):
    """Final SoA is pruned to union(text, vision) and ScheduleTimeline is derived.

    This test builds small, deterministic text and vision SoAs and a mocked
    LLM reconciliation output that introduces an extra activity/timepoint pair
    not present in either input. After running ``reconcile_soa``, the
    post-processing logic should:

    - Drop the extra (activityId, plannedTimepointId) pair from
      ``activityTimepoints``.
    - Rebuild a ``scheduleTimelines`` array with a single
      ``ScheduleTimeline`` object that has the required USDM fields
      (``instanceType``, ``mainTimeline``, ``entryCondition``, ``entryId``).
    - Ensure all ``ScheduledActivityInstance`` entries only reference
      activities/encounters that are present in the union of the inputs.
    """

    text_input_path = os.path.join(TEST_DATA_DIR, 'union_text_input.json')
    vision_input_path = os.path.join(TEST_DATA_DIR, 'union_vision_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'union_output.json')

    # Minimal, matching text and vision SoAs with a single valid tick
    base_timeline = {
        "activities": [
            {"id": "act1", "instanceType": "Activity"},
        ],
        "plannedTimepoints": [
            {"id": "tp1", "encounterId": "enc1", "instanceType": "PlannedTimepoint"},
        ],
        "encounters": [
            {"id": "enc1", "instanceType": "Encounter"},
        ],
        "activityTimepoints": [
            {"activityId": "act1", "plannedTimepointId": "tp1"},
        ],
    }

    text_soa = {"study": {"versions": [{"timeline": base_timeline}]}}
    vision_soa = {"study": {"versions": [{"timeline": base_timeline}]}}

    with open(text_input_path, 'w') as f:
        json.dump(text_soa, f)
    with open(vision_input_path, 'w') as f:
        json.dump(vision_soa, f)

    # Mock LLM reconciliation output that adds an extra activity/timepoint
    reconciled_timeline = {
        "activities": [
            {"id": "act1", "instanceType": "Activity"},
            {"id": "act2", "instanceType": "Activity"},  # extra
        ],
        "plannedTimepoints": [
            {"id": "tp1", "encounterId": "enc1", "instanceType": "PlannedTimepoint"},
            {"id": "tp2", "encounterId": "enc1", "instanceType": "PlannedTimepoint"},  # extra
        ],
        "encounters": [
            {"id": "enc1", "instanceType": "Encounter"},
        ],
        "activityTimepoints": [
            {"activityId": "act1", "plannedTimepointId": "tp1"},  # valid
            {"activityId": "act2", "plannedTimepointId": "tp2"},  # should be pruned
        ],
    }

    reconciled_data = {"study": {"versions": [{"timeline": reconciled_timeline}]}}

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(reconciled_data)
    mock_create.return_value = mock_response

    reconcile_soa(
        vision_path=vision_input_path,
        output_path=output_path,
        text_path=text_input_path,
        model_name='o3',
    )

    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        final_data = json.load(f)

    # Helper to get the first version's timeline
    timeline = (
        final_data.get('study', {})
        .get('versions', [{}])[0]
        .get('timeline', {})
    )

    # 1) activityTimepoints must be a subset of union(text, vision)
    allowed_pairs = {('act1', 'tp1')}
    final_pairs = set()
    for at in timeline.get('activityTimepoints', []):
        aid = at.get('activityId')
        pid = at.get('plannedTimepointId') or at.get('timepointId')
        if aid and pid:
            final_pairs.add((aid, pid))

    assert final_pairs.issubset(allowed_pairs)
    assert ('act2', 'tp2') not in final_pairs

    # 2) ScheduleTimeline is derived with required fields and only valid refs
    schedule_timelines = timeline.get('scheduleTimelines', [])
    assert schedule_timelines, "Expected a derived ScheduleTimeline to be present"

    st_obj = schedule_timelines[0]
    assert st_obj.get('instanceType') == 'ScheduleTimeline'
    assert st_obj.get('mainTimeline') is True
    assert isinstance(st_obj.get('entryCondition'), str)
    assert st_obj.get('entryId'), "ScheduleTimeline.entryId should be populated"

    instances = st_obj.get('instances', [])
    assert instances, "Expected at least one ScheduledActivityInstance"
    for inst in instances:
        assert inst.get('instanceType') == 'ScheduledActivityInstance'
        # All instances should reference only enc1 and act1
        assert inst.get('encounterId') == 'enc1'
        assert set(inst.get('activityIds', [])) <= {"act1"}
