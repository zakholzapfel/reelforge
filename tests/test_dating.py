import json
import threading
import time
import pytest
from fastapi.testclient import TestClient
from reelforge import dating
from reelforge.app import create_app
from reelforge.models import DateEvidence, DateFilter, Dating, Item, ReferenceEntry
from reelforge.store import Store


def item(title="Sample Library - Skyline Study (1080p HD)", **kw):
    return Item(id="promo",url="https://example.org/promo",title=title,**kw)


def catalog():
    return [ReferenceEntry(title=title,year_start=year,year_end=year,url="https://example.org/reference/"+str(index)) for index,(title,year) in enumerate([("Sample Library - Skyline Study",2000),("Sample Library - Harbor Study",2001),("Sample Library - Morning Study",2001),("Sample Library - Morning Study New Edition",2014)])]


def criteria(**values):
    return DateFilter(**({"year_start":2000,"year_end":2009}|values))


@pytest.mark.parametrize("title,expected",[("Sample Library - Skyline Study (1080p HD)",2000),("Sample Library - Harbor Study (4K)",2001),("Sample Library - Morning Study (1080p HD)",2001),("Sample Library - Morning Study New Edition",2014)])
def test_reference_matching_keeps_editions_separate(title,expected):
    result=dating.analyze(item(title),catalog())
    assert result.dating.confidence=="documented"
    assert result.dating.year_start==expected
    assert result.dating.evidence[0].url.startswith("https://example.org/reference/")
    assert not result.dating.reviewed


def test_no_reference_catalog_loaded_by_default():
    assert dating.analyze(item()).dating.confidence=="unknown"


def test_years_inside_work_titles_are_not_stripped_for_reference_matching():
    assert dating.normalized_title("2001 A Space Odyssey") != dating.normalized_title("2010 A Space Odyssey")


def test_user_supplied_aliases_work():
    reference=ReferenceEntry(title="Full source title",aliases=["Alternate title"],year_start=1995,year_end=1995,url="https://example.org/reference")
    assert dating.analyze(item("Alternate title (1080p HD)"),[reference]).dating.confidence=="documented"


def test_reference_catalogue_persists_without_builtins(tmp_path):
    app=create_app(tmp_path,token="test",start_worker=False)
    with TestClient(app,headers={"X-ReelForge-Token":"test"}) as client:
        assert client.get("/api/references").json()["records"]==[]
        data={"name":"My Research","records":[r.model_dump() for r in catalog()]}
        assert client.post("/api/references",json=data).json()["name"]=="My Research"
    app=create_app(tmp_path,token="test",start_worker=False)
    with TestClient(app,headers={"X-ReelForge-Token":"test"}) as client:
        assert len(client.get("/api/references").json()["records"])==4
        assert client.post("/api/references",json={"name":"Empty","records":[]}).status_code==200


def test_collection_scopes_are_user_defined():
    reference=ReferenceEntry(title="Shared Title",collection="Landscapes",year_start=2000,year_end=2000,url="https://example.org/reference")
    assert dating.analyze(item("Shared Title",collection="Jazz"),[reference]).dating.confidence=="unknown"
    assert dating.analyze(item("Shared Title",collection="Landscapes"),[reference]).dating.confidence=="documented"


def test_no_fuzzy_match_for_new_edit():
    assert dating.analyze(item("Sample Library - Skyline Study New Fan Edit"),catalog()).dating.confidence=="unknown"


def test_title_year_is_uploader_claim_not_documented():
    d=dating.analyze(item("Sample Library - Forest Walk 2005 Promo")).dating
    assert d.year_start==2005 and d.confidence=="likely"


@pytest.mark.parametrize("title",["Unidentified 1080p HD Promo","Unknown 25th Anniversary Promo 2022","Unknown remastered 2024","Unknown 1999 and 2020"])
def test_non_original_years_do_not_become_dates(title):
    assert dating.analyze(item(title)).dating.confidence=="unknown"


def test_upload_date_not_used():
    d=dating.analyze(item("Unknown promo",upload_date="20050801")).dating
    assert d.confidence=="unknown" and d.year_start is None


def test_decade_is_range_not_exact_year():
    d=dating.analyze(item("Sample Collection 2000s Video")).dating
    assert (d.year_start,d.year_end)==(2000,2009)
    assert dating.classify(d,2000,2005)=="overlap"


def test_description_airing_statement():
    d=dating.analyze(item("Unknown promo",description="Restored in 2024. This promo originally aired in November 2003. Music released in 1998.")).dating
    assert d.confidence=="likely" and d.year_start==2003


def test_original_publication_statement_is_content_neutral():
    d=dating.analyze(item("A lecture recording",description="This recording was originally published in 1996.")).dating
    assert d.year_start==1996 and d.confidence=="likely"


def test_description_copyright_and_music_dates_ignored():
    assert dating.analyze(item("Unknown promo",description="Uploaded in 2020. Copyright 2002. Music from the 2001 album.")).dating.confidence=="unknown"


def test_series_premiere_is_not_promo_airdate():
    assert dating.analyze(item("Unknown promo",description="The series originally aired in 1998. This show premiered in 1997.")).dating.confidence=="unknown"


def test_conflicting_evidence_not_selected():
    result=dating.analyze(item("Sample Library - Skyline Study (2001)"),catalog())
    assert result.dating.confidence=="conflicting"
    assert not dating.select_dates([result],criteria(confidence="likely"))


def test_range_must_be_wholly_within_target():
    a=item("2000-2009 Promo")
    b=item("1999-2001 Promo").model_copy(update={"id":"overlap"})
    analyzed=[dating.analyze(i) for i in [a,b]]
    assert dating.select_dates(analyzed,criteria(confidence="likely"))==["promo"]
    assert dating.classify(analyzed[1].dating,2000,2009)=="overlap"


def test_documented_only_does_not_select_likely():
    items=[dating.analyze(item(),catalog()),dating.analyze(item("Promo 2005").model_copy(update={"id":"claim"}))]
    assert dating.select_dates(items,criteria())==["promo"]
    assert dating.select_dates(items,criteria(confidence="likely"))==["promo","claim"]


def test_invalid_filter_range_rejected():
    with pytest.raises(ValueError):dating.select_dates([item()],criteria(year_start=2009,year_end=2000))


def test_review_overrides_conflict_and_survives_analysis():
    original=dating.analyze(item("Sample Library - Skyline Study (2001)"),catalog())
    result=dating.review(original,2000,2000,"documented","Exact original video matched archive.","https://example.org/reference")
    assert dating.analyze(result).dating==result.dating
    assert result.dating.reviewed and result.year==2000
    assert len(result.dating.evidence)==3


def test_review_requires_reason():
    with pytest.raises(ValueError,match="reasoning"):
        dating.review(item(),2000,2000,"documented","")


def test_cached_review_survives_reopening_db(tmp_path):
    store=Store(tmp_path/"state.sqlite3")
    result=dating.review(item(),2000,2000,"documented","Archive matched.")
    store.cache_date(result)
    store.close()
    store=Store(tmp_path/"state.sqlite3")
    assert store.restored_date(item()).dating.reviewed
    assert not store.restored_date(item("Changed title")).dating.reviewed
    store.close()


def test_reference_page_extracts_explicit_airdate_not_navigation(monkeypatch):
    monkeypatch.setattr(dating,"fetch",lambda url:'<nav>Archive 2026</nav><h1>Unlisted Promo</h1><div>Airdate</div><div>June 2004</div><h3>Song</h3><p>Song copyright 1998</p><footer>Copyright 2026</footer>')
    result=dating.reference_page(item("Unlisted Promo"),"https://example.org/archive")
    assert result.dating.year_start==2004 and result.dating.confidence=="likely"


def test_reference_page_ambiguous_dates_not_guessed(monkeypatch):
    monkeypatch.setattr(dating,"fetch",lambda url:'<h1>Promo</h1><p>Originally aired in 2000.</p><p>First aired in 2014.</p>')
    with pytest.raises(ValueError,match="unambiguous"):
        dating.reference_page(item("Promo"),"https://example.org/archive")


def test_manifest_round_trip_preserves_evidence():
    from reelforge.sources import manifest_scan
    original=dating.analyze(item(),catalog())
    result=manifest_scan(json.dumps([original.model_dump()]),"Collection")[0]
    assert result.dating==original.dating


def wait_task(client,rid):
    for _ in range(100):
        result=client.get("/api/dates/research/"+rid).json()
        if result["state"]!="running":return result
        time.sleep(.02)
    pytest.fail("Research did not finish.")


def test_research_selection_review_and_cache_api(tmp_path):
    app=create_app(tmp_path,token="test",start_worker=False)
    with TestClient(app,headers={"X-ReelForge-Token":"test"}) as client:
        assert client.post("/api/references",json={"name":"Test references","records":[r.model_dump() for r in catalog()]}).status_code==200
        rid=client.post("/api/dates/research",json={"items":[item().model_dump()],"descriptions":False}).json()["id"]
        result=wait_task(client,rid)
        assert result["state"]=="completed" and result["done"]==1
        assert result["items"][0]["dating"]["year_start"]==2000
        selected=client.post("/api/dates/select",json={"items":result["items"],"year_start":2000,"year_end":2009,"confidence":"documented"}).json()
        assert selected["ids"]==["promo"]
        review=client.post("/api/dates/review",json={"item":result["items"][0],"year_start":2002,"year_end":2002,"confidence":"likely","note":"Manual video clue."}).json()
        assert review["item"]["dating"]["reviewed"]
        rid2=client.post("/api/dates/research",json={"items":result["items"]}).json()["id"]
        assert wait_task(client,rid2)["items"][0]["dating"]["year_start"]==2002


def test_cancel_research_keeps_completed_results(tmp_path,monkeypatch):
    import reelforge.app as app_module
    entered=threading.Event()
    def slow(item,cancel):
        entered.set()
        cancel.wait(3)
        raise InterruptedError()
    monkeypatch.setattr(app_module,"metadata_description",slow)
    app=create_app(tmp_path,token="test",start_worker=False)
    with TestClient(app,headers={"X-ReelForge-Token":"test"}) as client:
        rid=client.post("/api/dates/research",json={"items":[item().model_dump()],"descriptions":True}).json()["id"]
        assert entered.wait(1)
        client.post("/api/dates/research/"+rid+"/cancel",json={})
        result=wait_task(client,rid)
        assert result["state"]=="cancelled" and result["done"]==0
