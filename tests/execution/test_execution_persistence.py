from __future__ import annotations

import hashlib
import math
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from controlled_evaluation import (
    ControlledEvaluationEngine, ControlledExecutionService, EvaluationRequest,
    ProviderResponse,
)
from controlled_models import ControlledRun, DatasetVersion, Experiment, ExperimentalCondition, ExperimentManifest, ExperimentalUnit, PassAttempt, RunPass
from controlled_persistence import ControlledPersistence, Outcome, PassObservation, to_json_safe
from controlled_real_execution import BudgetLedger, ExecutionCaps, RealExecutionProfile
from database import engine as live_postgres_engine
from mock_provider import MockScenario
from model_registry import Provider, get_model_spec
from models import Answer, Prompt


class SampleEnum(Enum):
    OPTION_A = 'OPTION_A'


class SamplePydantic(BaseModel):
    name: str
    amount: Decimal


@dataclass
class SampleDataclass:
    identifier: uuid.UUID
    cost: Decimal


class CustomFakeProvider:
    def __init__(self, scenarios: list[MockScenario], *, input_tokens: int | None = 599, output_tokens: int | None = 112, route_provenance: dict | None = None):
        self.scenarios = list(scenarios)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.route_provenance = route_provenance
        self.calls = 0

    def evaluate(self, request):
        scenario = self.scenarios.pop(0)
        self.calls += 1
        if scenario is MockScenario.TIMEOUT:
            raise TimeoutError('mock timeout')
        if scenario is MockScenario.REFUSAL:
            from controlled_evaluation import ProviderCallError
            raise ProviderCallError('REFUSAL', 'mock refusal')
        if scenario is MockScenario.PROVIDER_ERROR:
            from controlled_evaluation import ProviderCallError
            raise ProviderCallError('PROVIDER_ERROR', 'mock error')
        
        return ProviderResponse(
            raw_response={
                'verdict': scenario.value,
                'criteria_scores': {'correctness': 4, 'relevance': 4, 'completeness': 4, 'clarity': 4, 'safety': 5},
                'confidence': 0.85,
                'explanation': 'Mock reasoning explanation.',
            },
            effective_model='gpt-4o-mini-2024-07-18',
            model_version='2024-07-18',
            provider_response_id=f'fake-resp-{self.calls}',
            upstream_provider_model='Direct',
            route_provenance=self.route_provenance,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


def test_to_json_safe_handles_all_complex_types():
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4()
    p = Path('logs/attempt.json')

    data = {
        'decimal': Decimal('0.000105'),
        'uuid': uid,
        'datetime': now,
        'enum': SampleEnum.OPTION_A,
        'path': p,
        'nan': float('nan'),
        'inf': float('inf'),
        'pydantic': SamplePydantic(name='query', amount=Decimal('0.05')),
        'dataclass': SampleDataclass(identifier=uid, cost=Decimal('0.002')),
        'nested_list': [Decimal('1.23'), {'sub': Decimal('4.56')}],
    }

    safe = to_json_safe(data)
    assert safe['decimal'] == '0.000105'
    assert safe['uuid'] == str(uid)
    assert safe['datetime'] == now.isoformat()
    assert safe['enum'] == 'OPTION_A'
    assert safe['path'] == str(p)
    assert safe['nan'] is None
    assert safe['inf'] is None
    assert safe['pydantic'] == {'name': 'query', 'amount': '0.05'}
    assert safe['dataclass'] == {'identifier': str(uid), 'cost': '0.002'}
    assert safe['nested_list'] == ['1.23', {'sub': '4.56'}]

    import json
    serialized = json.dumps(safe)
    assert '0.000105' in serialized


def _setup_test_unit(session):
    prompt = Prompt(text='Which answer is better?', category='test')
    session.add(prompt)
    session.flush()
    a = Answer(prompt_id=prompt.id, model_name='author-a', text='Answer A text', word_count=3)
    b = Answer(prompt_id=prompt.id, model_name='author-b', text='Answer B text', word_count=3)
    session.add_all([a, b])
    session.flush()

    repo = ControlledPersistence(session)
    dataset = repo.get_or_create_dataset_version(
        source_name='regression-test', version='v1', source_checksum='d' * 64, import_status='SUCCEEDED',
    )
    experiment = repo.create_experiment(
        dataset_version=dataset, experiment_name='regression-exp', research_question='RQ', hypothesis='test',
    )
    condition = repo.create_condition(
        experiment=experiment, condition_code='BASELINE_STANDARD', label='base', condition_json={}, protocol_version='p1',
    )
    manifest = repo.create_manifest(
        experiment=experiment, rq_code='RQ1', protocol_version='p1', analysis_version='a1',
        dataset_snapshot_id='snap', dataset_checksum='e' * 64, manifest_sha256='f' * 64, manifest_json={},
    )
    unit = repo.register_unit(
        experiment=experiment, manifest=manifest, condition=condition, prompt_id=prompt.id,
        answer_a_id=a.id, answer_b_id=b.id, prompt_category='test', judge_model='gpt-4o-mini',
        provider='OPENAI', provider_model='gpt-4o-mini', prompt_template_version='controlled-judge-pairwise-v1',
        presentation_order='AB', repetition_index=0, randomization_block='block', data_split='test',
        inclusion_status='INCLUDED',
    )
    return repo, unit, a, b


def test_budget_reservation_and_persistence_roundtrip_offline(tmp_path):
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / 'json_test.sqlite'
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'alembic'))
    cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + db_path.as_posix())
    command.upgrade(cfg, 'head')
    test_engine = create_engine('sqlite:///' + db_path.as_posix())
    event.listen(test_engine, 'connect', lambda c, _: c.execute('PRAGMA foreign_keys=ON'))

    Session = sessionmaker(bind=test_engine)
    profile = RealExecutionProfile(
        execution_mode='PILOT', authorization_token='test-token', dataset_version_id='d-id',
        manifest_ids=('m-id',), manifest_hashes=('m-hash',), source_commit='c', source_tag='t',
        pricing_version='pricing-config-v1', routing_version='r-v', routing_fingerprint='r-fp',
        prompt_version='p-v', prompt_sha256='p-hash', retry_policy_version='retry-v2',
        failure_policy_version='fail-v2', analysis_version='a-v', model_ids=('gpt-4o-mini',),
        configured_upstreams=(), caps=ExecutionCaps(6, 8, 100_000, 3_000, Decimal('0.05')),
        evidence_class='PILOT',
    )

    with Session.begin() as session:
        repo, unit, a, b = _setup_test_unit(session)
        ledger = BudgetLedger(profile)

        spec = get_model_spec('gpt-4o-mini')
        req = EvaluationRequest(
            question='Test question', answer_a=a.text, answer_b=b.text, judge_name='gpt-4o-mini',
            provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0,
            seed=123, prompt_template_version='controlled-judge-pairwise-v1', experiment_id=unit.experiment_id,
            controlled_unit_id=unit.id, repetition_index=0, pass_number=1, original_answer_a_id=a.id,
            original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id,
        )

        fake = CustomFakeProvider([MockScenario.ANSWER_A], input_tokens=599, output_tokens=112)
        service = ControlledExecutionService(
            repo, ControlledEvaluationEngine(fake), evidence_class='PILOT',
            before_provider_attempt=lambda run, r: ledger.reserve(run_id=str(run.id), request=r),
            execution_metadata={'profile': profile.provenance_snapshot(), 'budget': ledger.snapshot()},
        )

        run = service.execute_single(unit=unit, request=req, idempotency_key='reg_key_01')
        assert run.status == 'SUCCEEDED'
        assert len(run.passes) == 1
        assert run.passes[0].outcome == 'ANSWER_A'

        attempt = session.scalar(select(PassAttempt).where(PassAttempt.run_id == run.id))
        assert attempt is not None
        assert attempt.state == 'SUCCEEDED'
        assert attempt.input_tokens == 599
        assert attempt.output_tokens == 112
        assert attempt.estimated_usd is not None
        assert attempt.actual_usd is not None
        assert isinstance(attempt.details_json, dict)
        assert 'estimated_usd' in attempt.details_json
        assert isinstance(attempt.details_json['estimated_usd'], str)


def test_postgresql_json_persistence_in_live_db_transaction_rollback():
    if str(live_postgres_engine.url).startswith('sqlite'):
        pytest.skip('PostgreSQL engine not configured')

    with live_postgres_engine.connect() as conn:
        trans = conn.begin()
        Session = sessionmaker(bind=conn)
        session = Session()
        try:
            repo, unit, a, b = _setup_test_unit(session)

            profile = RealExecutionProfile(
                execution_mode='PILOT', authorization_token='test-token', dataset_version_id='d-id',
                manifest_ids=('m-id',), manifest_hashes=('m-hash',), source_commit='c', source_tag='t',
                pricing_version='pricing-config-v1', routing_version='r-v', routing_fingerprint='r-fp',
                prompt_version='p-v', prompt_sha256='p-hash', retry_policy_version='retry-v2',
                failure_policy_version='fail-v2', analysis_version='a-v', model_ids=('gpt-4o-mini',),
                configured_upstreams=(), caps=ExecutionCaps(6, 8, 100_000, 3_000, Decimal('0.05')),
                evidence_class='PILOT',
            )
            ledger = BudgetLedger(profile)

            spec = get_model_spec('gpt-4o-mini')
            req = EvaluationRequest(
                question='Postgres serialization test', answer_a=a.text, answer_b=b.text, judge_name='gpt-4o-mini',
                provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0,
                seed=123, prompt_template_version='controlled-judge-pairwise-v1', experiment_id=unit.experiment_id,
                controlled_unit_id=unit.id, repetition_index=0, pass_number=1, original_answer_a_id=a.id,
                original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id,
            )

            fake = CustomFakeProvider(
                [MockScenario.ANSWER_A], input_tokens=599, output_tokens=112,
                route_provenance={'configured_upstream': 'amazon-bedrock', 'observed_upstream': 'amazon-bedrock', 'latency': Decimal('1.42')},
            )
            service = ControlledExecutionService(
                repo, ControlledEvaluationEngine(fake), evidence_class='PILOT',
                before_provider_attempt=lambda run, r: ledger.reserve(run_id=str(run.id), request=r),
                execution_metadata={'profile': profile.provenance_snapshot(), 'budget': ledger.snapshot()},
            )

            run = service.execute_single(unit=unit, request=req, idempotency_key='pg_reg_key_01')
            session.flush()

            assert run.status == 'SUCCEEDED'
            attempt = session.scalar(select(PassAttempt).where(PassAttempt.run_id == run.id))
            assert attempt is not None
            assert attempt.state == 'SUCCEEDED'
            assert attempt.details_json['estimated_usd'] is not None
            assert attempt.route_provenance_json['latency'] == '1.42'
        finally:
            session.close()
            trans.rollback()


def test_failure_path_json_safety(tmp_path):
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / 'json_fail_test.sqlite'
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'alembic'))
    cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + db_path.as_posix())
    command.upgrade(cfg, 'head')
    test_engine = create_engine('sqlite:///' + db_path.as_posix())
    event.listen(test_engine, 'connect', lambda c, _: c.execute('PRAGMA foreign_keys=ON'))

    Session = sessionmaker(bind=test_engine)
    with Session.begin() as session:
        repo, unit, a, b = _setup_test_unit(session)
        spec = get_model_spec('gpt-4o-mini')
        req = EvaluationRequest(
            question='Fail test', answer_a=a.text, answer_b=b.text, judge_name='gpt-4o-mini',
            provider=spec.provider, requested_model=spec.requested_model, temperature=0.0, top_p=1.0,
            seed=123, prompt_template_version='controlled-judge-pairwise-v1', experiment_id=unit.experiment_id,
            controlled_unit_id=unit.id, repetition_index=0, pass_number=1, original_answer_a_id=a.id,
            original_answer_b_id=b.id, presented_answer_a_id=a.id, presented_answer_b_id=b.id,
        )

        for scenario in [MockScenario.TIMEOUT, MockScenario.REFUSAL, MockScenario.PROVIDER_ERROR]:
            fake = CustomFakeProvider([scenario])
            service = ControlledExecutionService(repo, ControlledEvaluationEngine(fake), evidence_class='PILOT')
            run = service.execute_single(unit=unit, request=req, idempotency_key='fail_key_' + scenario.name)
            assert run.status == 'FAILED'
            attempt = session.scalar(select(PassAttempt).where(PassAttempt.run_id == run.id))
            assert attempt is not None
            assert attempt.state in {'FAILED_FINAL', 'FAILED_RETRYABLE'}
