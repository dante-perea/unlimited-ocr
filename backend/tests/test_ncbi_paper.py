"""Integration tests for GET /ncbi/paper/{pmcid}."""

from __future__ import annotations

from tests.conftest import NcbiMock, load_json, load_text


def _mock_for_paper(oa_filename: str) -> NcbiMock:
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {"PMC5334499": load_text(oa_filename)}
    return mock


def test_paper_returns_metadata_and_downloads(install_service, client):
    mock = _mock_for_paper("oa_pdf.xml")
    install_service(mock)

    resp = client.get("/ncbi/paper/PMC5334499")
    assert resp.status_code == 200
    body = resp.json()

    assert body["pmcid"] == "PMC5334499"
    assert body["pmid"] == "28373852"
    assert body["doi"] == "10.5327/wjr.v9.i2.27"
    assert "COVID-19" in body["title"]
    assert body["journal"] == "World Journal of Radiology"
    assert body["year"] == "2017"
    assert body["license"] == "CC BY-NC"
    assert body["retracted"] is False
    assert "World J Radiol" in body["citation"]

    # Abstract snippet fetched from PubMed.
    assert body["abstract_snippet"]
    assert "radiological" in body["abstract_snippet"]

    downloads = body["downloads"]
    formats = {d["format"] for d in downloads}
    assert formats == {"pdf", "tgz"}

    pdf = next(d for d in downloads if d["format"] == "pdf")
    # ftp:// must be converted to https://.
    assert str(pdf["url"]).startswith("https://ftp.ncbi.nlm.nih.gov/")
    assert str(pdf["url"]).endswith(".pdf")


def test_paper_accepts_numeric_pmcid(install_service, client):
    """A bare numeric id is normalized to PMC<digits>."""
    install_service(_mock_for_paper("oa_pdf.xml"))
    resp = client.get("/ncbi/paper/5334499")
    assert resp.status_code == 200
    assert resp.json()["pmcid"] == "PMC5334499"


def test_paper_not_found_via_oa_error(install_service, client):
    """When the OA service reports an error, a 404 is returned."""
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {}  # NcbiMock returns an <error> response for unknown ids
    install_service(mock)

    resp = client.get("/ncbi/paper/PMC0000000")
    assert resp.status_code == 404


def test_paper_invalid_pmcid(install_service, client):
    install_service(NcbiMock())
    resp = client.get("/ncbi/paper/not-a-pmc-id")
    assert resp.status_code == 400


def test_paper_only_tgz_download(install_service, client):
    """An article whose OA record only lists a tgz package is still returned."""
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {"PMC5334499": load_text("oa_tgz_only.xml")}
    install_service(mock)

    resp = client.get("/ncbi/paper/PMC5334499")
    assert resp.status_code == 200
    downloads = resp.json()["downloads"]
    formats = {d["format"] for d in downloads}
    assert formats == {"tgz"}
