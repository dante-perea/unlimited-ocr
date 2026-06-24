"""Integration tests for GET /ncbi/search."""

from __future__ import annotations

from tests.conftest import NcbiMock, load_json


def test_search_returns_summaries(install_service, client):
    """ESearch + ESummary + EFetch are wired into a paginated response."""
    mock = NcbiMock()
    install_service(mock)

    resp = client.get("/ncbi/search", params={"query": "covid"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "covid"
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_results"] == 2
    assert body["total_pages"] == 1

    results = body["results"]
    assert len(results) == 2

    first = results[0]
    assert first["pmcid"] == "PMC5334499"
    assert first["pmid"] == "28373852"
    assert first["doi"] == "10.5327/wjr.v9.i2.27"
    assert "COVID-19" in first["title"]
    assert first["journal"] == "World Journal of Radiology"
    assert first["year"] == "2017"
    assert [a["name"] for a in first["authors"]] == ["Smith John", "Doe Jane"]
    # Abstract snippet should be populated from the EFetch abstract step.
    assert first["abstract_snippet"]
    assert "radiological" in first["abstract_snippet"]


def test_search_term_includes_open_access_filter(install_service, client):
    """The 'open access[filter]' clause is appended to the query term."""
    mock = NcbiMock()
    captured: dict[str, str] = {}
    original = mock.__call__

    def recording(request):  # noqa: ANN001
        if request.url.path.endswith("/esearch.fcgi"):
            captured["term"] = request.url.params.get("term", "")
        return original(request)

    install_service(recording)

    client.get("/ncbi/search", params={"query": "machine learning"})

    assert "machine learning" in captured["term"]
    assert "open access[filter]" in captured["term"]


def test_search_pagination_metadata(install_service, client):
    """total_pages is derived from count / page_size."""
    mock = NcbiMock()
    payload = load_json("esearch_two.json")
    payload["esearchresult"]["count"] = "45"  # 3 pages at 20/page
    mock.esearch = payload
    install_service(mock)

    resp = client.get("/ncbi/search", params={"query": "x", "page": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_results"] == 45
    assert body["total_pages"] == 3
    assert body["page"] == 2


def test_search_empty_query_is_rejected(install_service, client):
    install_service(NcbiMock())
    resp = client.get("/ncbi/search", params={"query": "   "})
    assert resp.status_code == 400


def test_search_api_key_present_when_configured(install_service, client):
    """When an API key is configured it is forwarded on every E-utility call."""
    mock = NcbiMock()
    seen_keys: list[str] = []
    original = mock.__call__

    def recording(request):  # noqa: ANN001
        seen_keys.append(request.url.params.get("api_key", ""))
        return original(request)

    install_service(recording, api_key="SECRET123")

    client.get("/ncbi/search", params={"query": "covid"})

    assert seen_keys, "expected at least one E-utility request"
    assert all(k == "SECRET123" for k in seen_keys)


def test_search_api_key_absent_by_default(install_service, client):
    """Without a key the api_key param is omitted (3 req/s limit applies)."""
    mock = NcbiMock()
    seen_keys: list[str] = []
    original = mock.__call__

    def recording(request):  # noqa: ANN001
        seen_keys.append(request.url.params.get("api_key", ""))
        return original(request)

    install_service(recording)

    client.get("/ncbi/search", params={"query": "covid"})

    assert all(k == "" for k in seen_keys)
