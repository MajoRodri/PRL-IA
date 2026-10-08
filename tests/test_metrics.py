from types import SimpleNamespace
import pytest
from src import llm_service, rag_chain

@pytest.mark.parametrize('metadata,expected', [
    ({'usage_metadata': {'input_tokens': 20, 'output_tokens': 4, 'total_tokens': 24}}, (20,4,24)),
    ({'response_metadata': {'token_usage': {'prompt_tokens': 10, 'completion_tokens': 0, 'total_tokens': 10}}}, (10,0,10)),
    ({}, (None,None,None)),
    ({'usage_metadata': {'input_tokens': -1, 'output_tokens': True, 'total_tokens': '12'}}, (None,None,None)),
])
def test_provider_usage(monkeypatch, metadata, expected):
    response = SimpleNamespace(content='Respuesta', **metadata)
    monkeypatch.setattr(llm_service, 'get_llm', lambda: SimpleNamespace(invoke=lambda prompt: response))
    result = llm_service.generate_response_with_metrics('Pregunta')
    assert result['answer'] == 'Respuesta'
    assert tuple(result['metrics'].values()) == expected

@pytest.mark.parametrize('hits', [[], [{'text': 'Documento', 'metadata': {'source': 'demo.txt', 'page': 1}, 'distance': 0.1}]])
def test_metrics_through_rag(monkeypatch, hits):
    monkeypatch.setattr(rag_chain.vector_store, 'search', lambda *a, **kw: hits)
    calls = []
    usage = {'input_tokens': 25, 'output_tokens': 5, 'total_tokens': 30}
    def generate(prompt):
        calls.append(prompt)
        return {'answer': 'Respuesta', 'metrics': usage}
    monkeypatch.setattr(rag_chain, 'generate_response_with_metrics', generate)
    result = rag_chain.answer_query('Pregunta')
    assert result['metrics'] == usage
    assert result['answer'] == 'Respuesta'
    assert len(calls) == 1


def test_api_preserves_usage_and_measures_time(monkeypatch):
    from fastapi.testclient import TestClient
    from src import api
    usage = {'input_tokens': 30, 'output_tokens': 5, 'total_tokens': 35}
    monkeypatch.setattr(api, 'answer_query', lambda *a, **kw: {'answer': 'OK', 'sources': [], 'metrics': usage})
    ticks = iter([10.0, 10.125])
    monkeypatch.setattr(api, 'perf_counter', lambda: next(ticks))
    result = TestClient(api.app).post('/api/query', json={'question': 'Hola'}).json()
    assert result['metrics'] == {**usage, 'server_latency_ms': 125.0}
    assert 'server_latency_ms' not in usage
