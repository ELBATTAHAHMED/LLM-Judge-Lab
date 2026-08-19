from __future__ import annotations

import sys, uuid
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from controlled_evaluation import ControlledEvaluationEngine, ControlledExecutionService, EvaluationRequest
from controlled_models import ControlledRun, DatasetVersion, Experiment, ExperimentalCondition, ExperimentManifest, ExperimentalUnit, PassAttempt, RunPass
from controlled_persistence import ControlledPersistence, Outcome
from controlled_providers import ControlledChatAdapter, ProviderExecutionGate
from database import engine as live_postgres_engine
from model_registry import Provider, get_model_spec
from models import Answer, Prompt
from routing_policy import extract_openrouter_routing_metadata, normalize_provider_slug, validate_router_response

def test_fixture_a_top_level_provider_string():
    resp = {'id': 'gen-a', 'model': 'anthropic/claude-3-haiku', 'provider': 'Amazon Bedrock'}
    raw, canonical, fallback, meta = extract_openrouter_routing_metadata(resp)
    assert raw == 'Amazon Bedrock'
    assert canonical == 'amazon-bedrock'
    assert fallback is False
    assert meta['provider_string'] == 'Amazon Bedrock'
    validated = validate_router_response(judge_name='anthropic/claude-3-haiku', response=resp)
    assert validated['configured_upstream_provider'] == 'amazon-bedrock'
    assert validated['observed_upstream_provider'] == 'amazon-bedrock'
    assert validated['raw_observed_upstream_provider'] == 'Amazon Bedrock'
    assert validated['route_verification_basis'] == 'RESPONSE_CONFIRMED_EXACT_PROVIDER'
    assert validated['fallback_observed'] is False

def test_fixture_b_official_openrouter_metadata_object():
    resp = {
        'id': 'gen-b',
        'model': 'anthropic/claude-3-haiku',
        'openrouter_metadata': {
            'endpoints': [{'provider_name': 'Amazon Bedrock', 'provider_slug': 'amazon-bedrock'}],
            'attempts': [{'provider': 'Amazon Bedrock', 'status': 200}],
        },
    }
    raw, canonical, fallback, meta = extract_openrouter_routing_metadata(resp)
    assert raw == 'amazon-bedrock'
    assert canonical == 'amazon-bedrock'
    assert fallback is False
    validated = validate_router_response(judge_name='anthropic/claude-3-haiku', response=resp)
    assert validated['observed_upstream_provider'] == 'amazon-bedrock'
    assert validated['route_verification_basis'] == 'RESPONSE_CONFIRMED_EXACT_PROVIDER'

def test_fixture_c_both_forms_present_precedence():
    resp = {
        'id': 'gen-c',
        'model': 'anthropic/claude-3-haiku',
        'openrouter_metadata': {
            'endpoints': [{'provider_slug': 'amazon-bedrock'}],
        },
        'provider': 'Other Provider',
    }
    raw, canonical, fallback, meta = extract_openrouter_routing_metadata(resp)
    assert raw == 'amazon-bedrock'
    assert canonical == 'amazon-bedrock'

def test_fixture_d_provider_dictionary():
    resp = {
        'id': 'gen-d',
        'model': 'anthropic/claude-3-haiku',
        'provider': {'provider': 'amazon-bedrock', 'fallbacks': []},
    }
    raw, canonical, fallback, meta = extract_openrouter_routing_metadata(resp)
    assert raw == 'amazon-bedrock'
    assert canonical == 'amazon-bedrock'
    assert fallback is False

def test_fixture_e_missing_routing_metadata_fails_closed():
    resp = {'id': 'gen-e', 'model': 'anthropic/claude-3-haiku'}
    with pytest.raises(ValueError, match='missing required router metadata'):
        validate_router_response(judge_name='anthropic/claude-3-haiku', response=resp)

def test_fixture_f_wrong_provider_fails_provenance():
    resp = {'id': 'gen-f', 'model': 'anthropic/claude-3-haiku', 'provider': 'Google Vertex'}
    with pytest.raises(ValueError, match='unexpected upstream provider'):
        validate_router_response(judge_name='anthropic/claude-3-haiku', response=resp)

def test_fixture_g_fallback_multi_attempt_fails_closed():
    resp = {
        'id': 'gen-g',
        'model': 'anthropic/claude-3-haiku',
        'openrouter_metadata': {
            'endpoints': [{'provider_slug': 'amazon-bedrock'}],
            'attempts': [{'provider': 'other', 'status': 500}, {'provider': 'amazon-bedrock', 'status': 200}],
        },
    }
    with pytest.raises(ValueError, match='fallback metadata is forbidden'):
        validate_router_response(judge_name='anthropic/claude-3-haiku', response=resp)

def test_streamlake_normalization():
    for variant in ['StreamLake', 'streamlake', 'Stream Lake', 'stream-lake', 'stream_lake']:
        resp = {'id': 'gen-sl', 'model': 'deepseek/deepseek-chat', 'provider': variant}
        validated = validate_router_response(judge_name='deepseek/deepseek-chat', response=resp)
        assert validated['observed_upstream_provider'] == 'streamlake'
        assert validated['raw_observed_upstream_provider'] == variant
        assert validated['route_verification_basis'] == 'RESPONSE_CONFIRMED_EXACT_PROVIDER'

def test_claude_amazon_bedrock_and_generic_amazon_rejected():
    for variant in ['Amazon Bedrock', 'amazon-bedrock', 'amazonbedrock', 'bedrock']:
        resp = {'id': 'gen-cb', 'model': 'anthropic/claude-3-haiku', 'provider': variant}
        validated = validate_router_response(judge_name='anthropic/claude-3-haiku', response=resp)
        assert validated['observed_upstream_provider'] == 'amazon-bedrock'
        assert validated['route_verification_basis'] == 'RESPONSE_CONFIRMED_EXACT_PROVIDER'
    resp_generic = {'id': 'gen-bad', 'model': 'anthropic/claude-3-haiku', 'provider': 'amazon'}
    with pytest.raises(ValueError, match='unexpected upstream provider'):
        validate_router_response(judge_name='anthropic/claude-3-haiku', response=resp_generic)

def test_llama_case_a_request_enforced_turbo_response_confirmed_family():
    payload_a = {'provider': {'order': ['deepinfra/turbo'], 'only': ['deepinfra/turbo'], 'allow_fallbacks': False, 'require_parameters': True}}
    resp_a = {
        'id': 'gen-di-a',
        'model': 'meta-llama/llama-3.3-70b-instruct',
        'provider': 'DeepInfra',
        'openrouter_metadata': {
            'strategy': 'direct',
            'attempt': 1,
            'endpoints': {'available': [{'provider': 'DeepInfra', 'selected': True}]},
        },
    }
    validated = validate_router_response(judge_name='meta-llama/llama-3.3-70b-instruct', response=resp_a, request_payload=payload_a)
    assert validated['configured_upstream_provider'] == 'deepinfra/turbo'
    assert validated['observed_upstream_provider'] == 'deepinfra/turbo'
    assert validated['observed_provider_family'] == 'deepinfra'
    assert validated['observed_endpoint_slug'] is None
    assert validated['route_verification_basis'] == 'REQUEST_ENFORCED_EXACT_ENDPOINT_RESPONSE_CONFIRMED_FAMILY'

def test_llama_case_b_outbound_only_contains_family_only_fails():
    payload_b = {'provider': {'order': ['deepinfra'], 'only': ['deepinfra'], 'allow_fallbacks': False}}
    resp = {'id': 'gen-di-b', 'model': 'meta-llama/llama-3.3-70b-instruct', 'provider': 'DeepInfra'}
    with pytest.raises(ValueError, match="did not enforce required exact endpoint 'deepinfra/turbo'"):
        validate_router_response(judge_name='meta-llama/llama-3.3-70b-instruct', response=resp, request_payload=payload_b)

def test_llama_case_c_outbound_only_missing_fails():
    payload_c = {'provider': {'allow_fallbacks': False}}
    resp = {'id': 'gen-di-c', 'model': 'meta-llama/llama-3.3-70b-instruct', 'provider': 'DeepInfra'}
    with pytest.raises(ValueError, match="did not enforce required exact endpoint 'deepinfra/turbo'"):
        validate_router_response(judge_name='meta-llama/llama-3.3-70b-instruct', response=resp, request_payload=payload_c)

def test_llama_case_d_outbound_allow_fallbacks_true_fails():
    payload_d = {'provider': {'order': ['deepinfra/turbo'], 'only': ['deepinfra/turbo'], 'allow_fallbacks': True}}
    resp = {'id': 'gen-di-d', 'model': 'meta-llama/llama-3.3-70b-instruct', 'provider': 'DeepInfra'}
    with pytest.raises(ValueError, match='Outbound request allowed fallbacks'):
        validate_router_response(judge_name='meta-llama/llama-3.3-70b-instruct', response=resp, request_payload=payload_d)

def test_llama_case_e_other_provider_fails():
    payload_e = {'provider': {'order': ['deepinfra/turbo'], 'only': ['deepinfra/turbo'], 'allow_fallbacks': False}}
    resp = {'id': 'gen-di-e', 'model': 'meta-llama/llama-3.3-70b-instruct', 'provider': 'Google'}
    with pytest.raises(ValueError, match='unexpected upstream provider'):
        validate_router_response(judge_name='meta-llama/llama-3.3-70b-instruct', response=resp, request_payload=payload_e)

def test_llama_case_f_exact_endpoint_slug_in_response_passes():
    payload_f = {'provider': {'order': ['deepinfra/turbo'], 'only': ['deepinfra/turbo'], 'allow_fallbacks': False}}
    resp_exact = {
        'id': 'gen-di-f',
        'model': 'meta-llama/llama-3.3-70b-instruct',
        'openrouter_metadata': {
            'endpoints': [{'provider_slug': 'deepinfra/turbo', 'selected': True}],
            'attempts': [{'provider_slug': 'deepinfra/turbo', 'status': 200}],
        },
    }
    validated = validate_router_response(judge_name='meta-llama/llama-3.3-70b-instruct', response=resp_exact, request_payload=payload_f)
    assert validated['configured_upstream_provider'] == 'deepinfra/turbo'
    assert validated['observed_upstream_provider'] == 'deepinfra/turbo'
    assert validated['observed_provider_family'] == 'deepinfra'
    assert validated['observed_endpoint_slug'] == 'deepinfra/turbo'
    assert validated['route_verification_basis'] == 'RESPONSE_CONFIRMED_EXACT_ENDPOINT'

def _setup_test_unit(session, judge_model='anthropic/claude-3-haiku'):
    prompt = Prompt(text='Which answer is better?', category='test')
    session.add(prompt)
    session.flush()
    a = Answer(prompt_id=prompt.id, model_name='author-a', text='Answer A text', word_count=3)
    b = Answer(prompt_id=prompt.id, model_name='author-b', text='Answer B text', word_count=3)
    session.add_all([a, b])
    session.flush()
    repo = ControlledPersistence(session)
    dataset = repo.get_or_create_dataset_version(source_name='openrouter-test', version='v1', source_checksum='d' * 64, import_status='SUCCEEDED')
    experiment = repo.create_experiment(dataset_version=dataset, experiment_name='or-exp', research_question='RQ', hypothesis='test')
    condition = repo.create_condition(experiment=experiment, condition_code='BASELINE_STANDARD', label='base', condition_json={}, protocol_version='p1')
    manifest = repo.create_manifest(experiment=experiment, rq_code='RQ1', protocol_version='p1', analysis_version='a1', dataset_snapshot_id='snap', dataset_checksum='e' * 64, manifest_sha256='f' * 64, manifest_json={})
    unit = repo.register_unit(experiment=experiment, manifest=manifest, condition=condition, prompt_id=prompt.id, answer_a_id=a.id, answer_b_id=b.id, prompt_category='test', judge_model=judge_model, provider='OPENROUTER', provider_model=judge_model, prompt_template_version='controlled-judge-pairwise-v1', presentation_order='AB', repetition_index=0, randomization_block='block', data_split='test', inclusion_status='INCLUDED')
    return repo, unit, a, b

def test_openrouter_usage_cost_present_persists_as_authoritative(tmp_path):
    from alembic import command
    from alembic.config import Config
    db_path = tmp_path / 'or_cost_present.sqlite'
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'alembic'))
    cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + db_path.as_posix())
    command.upgrade(cfg, 'head')
    test_engine = create_engine('sqlite:///' + db_path.as_posix())
    event.listen(test_engine, 'connect', lambda c, _: c.execute('PRAGMA foreign_keys=ON'))
    Session = sessionmaker(bind=test_engine)
    with Session.begin() as session:
        repo, unit, a, b = _setup_test_unit(session)
        spec = get_model_spec('anthropic/claude-3-haiku')
        req = EvaluationRequest(question='Question', answer_a=a.text, answer_b=b.text, judge_name='anthropic/claude-3-haiku', provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0, seed=None, prompt_template_version='controlled-judge-pairwise-v1', experiment_id=unit.experiment_id, controlled_unit_id=unit.id, repetition_index=0, pass_number=1, original_answer_a_id=a.id, original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id)
        def transport(_endpoint, _headers, _payload):
            return {
                'id': 'gen-cost-1',
                'model': 'anthropic/claude-3-haiku',
                'provider': 'Amazon Bedrock',
                'usage': {'prompt_tokens': 600, 'completion_tokens': 150, 'total_tokens': 750, 'cost': 0.00018500},
                'choices': [{'message': {'content': '{"verdict":"ANSWER_A","criteria_scores":{"correctness":5,"relevance":5,"completeness":5,"clarity":5,"safety":5},"confidence":0.9,"explanation":"Clear explanation"}'}}],
            }
        gate = ProviderExecutionGate(mode='REAL', authorization_token='tok', verified_pricing_version='v1', max_provider_calls=1, max_input_tokens=1000, max_output_tokens=1000, max_usd=1.0)
        adapter = ControlledChatAdapter(provider=Provider.OPENROUTER, transport=transport, gate=gate)
        engine = ControlledEvaluationEngine(adapter)
        service = ControlledExecutionService(repo, engine, evidence_class='PILOT')
        run = service.execute_single(unit=unit, request=req, idempotency_key='cost_present_01')
        assert run.status == 'SUCCEEDED'
        attempt = session.scalar(select(PassAttempt).where(PassAttempt.run_id == run.id))
        assert attempt is not None
        assert attempt.state == 'SUCCEEDED'
        assert attempt.input_tokens == 600
        assert attempt.output_tokens == 150
        assert attempt.actual_usd == Decimal('0.00018500')
        assert attempt.details_json['cost_source'] == 'PROVIDER_REPORTED'
        assert attempt.details_json['provider_reported_usd'] == '0.000185'
        assert 'locally_computed_usd' in attempt.details_json
        assert 'cost_delta_usd' in attempt.details_json

def test_openrouter_usage_cost_absent_falls_back_to_local_computed(tmp_path):
    from alembic import command
    from alembic.config import Config
    db_path = tmp_path / 'or_cost_absent.sqlite'
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'alembic'))
    cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + db_path.as_posix())
    command.upgrade(cfg, 'head')
    test_engine = create_engine('sqlite:///' + db_path.as_posix())
    event.listen(test_engine, 'connect', lambda c, _: c.execute('PRAGMA foreign_keys=ON'))
    Session = sessionmaker(bind=test_engine)
    with Session.begin() as session:
        repo, unit, a, b = _setup_test_unit(session)
        spec = get_model_spec('anthropic/claude-3-haiku')
        req = EvaluationRequest(question='Question', answer_a=a.text, answer_b=b.text, judge_name='anthropic/claude-3-haiku', provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0, seed=None, prompt_template_version='controlled-judge-pairwise-v1', experiment_id=unit.experiment_id, controlled_unit_id=unit.id, repetition_index=0, pass_number=1, original_answer_a_id=a.id, original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id)
        def transport(_endpoint, _headers, _payload):
            return {
                'id': 'gen-cost-absent',
                'model': 'anthropic/claude-3-haiku',
                'provider': 'Amazon Bedrock',
                'usage': {'prompt_tokens': 600, 'completion_tokens': 150, 'total_tokens': 750},
                'choices': [{'message': {'content': '{"verdict":"ANSWER_A","criteria_scores":{"correctness":5,"relevance":5,"completeness":5,"clarity":5,"safety":5},"confidence":0.9,"explanation":"Clear explanation"}'}}],
            }
        gate = ProviderExecutionGate(mode='REAL', authorization_token='tok', verified_pricing_version='v1', max_provider_calls=1, max_input_tokens=1000, max_output_tokens=1000, max_usd=1.0)
        adapter = ControlledChatAdapter(provider=Provider.OPENROUTER, transport=transport, gate=gate)
        engine = ControlledEvaluationEngine(adapter)
        service = ControlledExecutionService(repo, engine, evidence_class='PILOT')
        run = service.execute_single(unit=unit, request=req, idempotency_key='cost_absent_01')
        assert run.status == 'SUCCEEDED'
        attempt = session.scalar(select(PassAttempt).where(PassAttempt.run_id == run.id))
        assert attempt is not None
        assert attempt.actual_usd is not None
        assert attempt.actual_usd > Decimal('0')
        assert attempt.details_json['cost_source'] == 'LOCAL_COMPUTED'

def test_openrouter_provenance_mismatch_with_cost_persists(tmp_path):
    from alembic import command
    from alembic.config import Config
    db_path = tmp_path / 'or_fail_cost.sqlite'
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'alembic'))
    cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + db_path.as_posix())
    command.upgrade(cfg, 'head')
    test_engine = create_engine('sqlite:///' + db_path.as_posix())
    event.listen(test_engine, 'connect', lambda c, _: c.execute('PRAGMA foreign_keys=ON'))
    Session = sessionmaker(bind=test_engine)
    with Session.begin() as session:
        repo, unit, a, b = _setup_test_unit(session)
        spec = get_model_spec('anthropic/claude-3-haiku')
        req = EvaluationRequest(question='Question', answer_a=a.text, answer_b=b.text, judge_name='anthropic/claude-3-haiku', provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0, seed=None, prompt_template_version='controlled-judge-pairwise-v1', experiment_id=unit.experiment_id, controlled_unit_id=unit.id, repetition_index=0, pass_number=1, original_answer_a_id=a.id, original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id)
        def transport(_endpoint, _headers, _payload):
            return {
                'id': 'gen-fail-cost',
                'model': 'anthropic/claude-3-haiku',
                'provider': 'Google Vertex',
                'usage': {'prompt_tokens': 599, 'completion_tokens': 120, 'total_tokens': 719, 'cost': 0.00015000},
                'choices': [{'message': {'content': '{"verdict":"ANSWER_A","criteria_scores":{"correctness":4,"relevance":4,"completeness":4,"clarity":4,"safety":5},"confidence":0.8,"explanation":"test"}'}}],
            }
        gate = ProviderExecutionGate(mode='REAL', authorization_token='tok', verified_pricing_version='v1', max_provider_calls=1, max_input_tokens=1000, max_output_tokens=1000, max_usd=1.0)
        adapter = ControlledChatAdapter(provider=Provider.OPENROUTER, transport=transport, gate=gate)
        engine = ControlledEvaluationEngine(adapter)
        service = ControlledExecutionService(repo, engine, evidence_class='PILOT')
        run = service.execute_single(unit=unit, request=req, idempotency_key='fail_cost_01')
        assert run.status == 'FAILED'
        assert run.error_code == 'PROVENANCE_MISMATCH'
        attempt = session.scalar(select(PassAttempt).where(PassAttempt.run_id == run.id))
        assert attempt is not None
        assert attempt.state == 'FAILED_FINAL'
        assert attempt.input_tokens == 599
        assert attempt.output_tokens == 120
        assert attempt.actual_usd == Decimal('0.00015000')
        assert attempt.details_json['cost_source'] == 'PROVIDER_REPORTED'

def test_postgresql_openrouter_exact_route_and_cost_regression():
    if str(live_postgres_engine.url).startswith('sqlite'):
        pytest.skip('PostgreSQL engine not configured')
    with live_postgres_engine.connect() as conn:
        trans = conn.begin()
        Session = sessionmaker(bind=conn)
        session = Session()
        try:
            repo, unit, a, b = _setup_test_unit(session, judge_model='meta-llama/llama-3.3-70b-instruct')
            spec = get_model_spec('meta-llama/llama-3.3-70b-instruct')
            req = EvaluationRequest(question='Question', answer_a=a.text, answer_b=b.text, judge_name='meta-llama/llama-3.3-70b-instruct', provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0, seed=None, prompt_template_version='controlled-judge-pairwise-v1', experiment_id=unit.experiment_id, controlled_unit_id=unit.id, repetition_index=0, pass_number=1, original_answer_a_id=a.id, original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id)
            def success_transport(_endpoint, _headers, _payload):
                return {
                    'id': 'gen-llama-pg',
                    'model': 'meta-llama/llama-3.3-70b-instruct',
                    'provider': 'DeepInfra',
                    'openrouter_metadata': {'endpoints': {'available': [{'provider': 'DeepInfra', 'selected': True}]}},
                    'usage': {'prompt_tokens': 600, 'completion_tokens': 150, 'total_tokens': 750, 'cost': 0.00021000},
                    'choices': [{'message': {'content': '{"verdict":"ANSWER_A","criteria_scores":{"correctness":5,"relevance":5,"completeness":5,"clarity":5,"safety":5},"confidence":0.9,"explanation":"Clear explanation"}'}}],
                }
            gate = ProviderExecutionGate(mode='REAL', authorization_token='tok', verified_pricing_version='v1', max_provider_calls=1, max_input_tokens=1000, max_output_tokens=1000, max_usd=1.0)
            adapter = ControlledChatAdapter(provider=Provider.OPENROUTER, transport=success_transport, gate=gate)
            engine = ControlledEvaluationEngine(adapter)
            service = ControlledExecutionService(repo, engine, evidence_class='PILOT')
            run = service.execute_single(unit=unit, request=req, idempotency_key='succ_llama_pg_01')
            session.flush()
            assert run.status == 'SUCCEEDED'
            attempt = session.scalar(select(PassAttempt).where(PassAttempt.run_id == run.id))
            assert attempt is not None
            assert attempt.state == 'SUCCEEDED'
            assert attempt.input_tokens == 600
            assert attempt.actual_usd == Decimal('0.00021000')
            assert attempt.route_provenance_json['observed_upstream_provider'] == 'deepinfra/turbo'
            assert attempt.route_provenance_json['observed_provider_family'] == 'deepinfra'
            assert attempt.route_provenance_json['observed_endpoint_slug'] is None
            assert attempt.route_provenance_json['route_verification_basis'] == 'REQUEST_ENFORCED_EXACT_ENDPOINT_RESPONSE_CONFIRMED_FAMILY'
        finally:
            session.close()
            trans.rollback()
