"""Optional browser smoke test; runs against an isolated local app with no download worker."""
import os
import json
import socket
import tempfile
import threading
import time
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright
from reelforge.app import create_app

def wait_until(page, predicate, timeout=30):
    # Evaluate the predicate directly: older browser drivers implement
    # wait_for_function with eval(), which the app deliberately blocks via CSP.
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if page.evaluate(predicate):
            return
        time.sleep(.05)
    raise AssertionError("Timed out waiting for browser state: "+predicate)


def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        sock=socket.socket()
        sock.bind(("127.0.0.1",0))
        sock.listen(128)
        port=sock.getsockname()[1]
        app=create_app(root/"state",token="gui-test-session",start_worker=False)
        @app.get("/fixture/index.json")
        def index_fixture():
            return {"payload":{"videos":[{"media":{"url":"https://example.org/owned-media.mp4"},"name":"Example session","episode":1}]}}
        server=uvicorn.Server(uvicorn.Config(app,log_level="error"))
        thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True)
        thread.start()
        while not server.started:
            time.sleep(.05)
        errors=[]
        try:
            with sync_playwright() as p:
                kwargs={"headless":True}
                if os.environ.get("REELFORGE_BROWSER"):
                    kwargs["executable_path"]=os.environ["REELFORGE_BROWSER"]
                browser=p.chromium.launch(**kwargs)
                page=browser.new_page(viewport={"width":1440,"height":1100})
                page.on("pageerror",lambda error:errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}/#token=gui-test-session")
                wait_until(page,"() => document.getElementById('system-pill').textContent.includes('Engine')")
                page.locator("#root").fill(str(root/"media"))
                page.locator("#demo").click()
                wait_until(page,"() => document.querySelectorAll('.video-row').length===4")
                wait_until(page,"() => document.getElementById('first-preview').textContent.includes('S01E01')")
                assert page.locator("#queue-selected").is_disabled()
                before_help=page.locator("#selected-count").inner_text()
                page.locator('.source-footer [data-help="help-start"]').click()
                assert page.locator("#help").is_visible()
                assert page.locator("#view-label").inner_text()=="Help & guide"
                assert page.locator("#help-start h2").evaluate("el => el===document.activeElement")
                page.locator('.help-jumps [data-help="help-faq"]').click()
                page.locator("#faq-search").fill("likely")
                matching=page.locator("#help-faq details:not([hidden])")
                assert matching.count()>=1
                assert all(matching.nth(i).evaluate("el => el.open") for i in range(matching.count()))
                page.locator("#faq-search").fill("no-such-question-xyz")
                assert page.locator("#faq-empty").is_visible()
                assert page.locator("#faq-count").inner_text()=="0 questions"
                page.locator("#faq-search").fill("")
                assert page.locator("#help-faq details:not([hidden])").count()==12
                summary=page.locator("#help-faq summary").first
                summary.focus()
                summary.press("Enter")
                assert page.locator("#help-faq details").first.evaluate("el => el.open")
                page.locator('#help [data-view="ingest"]').click()
                assert page.locator("#selected-count").inner_text()==before_help
                assert page.locator(".video-row").count()==4
                page.locator('.dates-card [data-help="help-dates"]').click()
                assert page.locator("#help-dates h2").evaluate("el => el===document.activeElement")
                page.locator('#help [data-view="ingest"]').click()
                page.locator("#search").fill("Winter")
                assert page.locator(".video-row").count()==1
                page.locator("#search").fill("")
                page.locator("[data-edit]").first.click()
                assert page.locator("#edit-season").input_value()=="1"
                page.locator("#edit-form button[value=cancel]").last.click()
                page.locator("#browse").click()
                wait_until(page,"() => document.getElementById('folder-path').value.length>0")
                page.locator("#folder-path").fill(str(root))
                page.locator("#folder-go").click()
                wait_until(page,"() => document.getElementById('folder-path').value.includes('tmp')")
                page.locator("#folder-close").click()
                page.locator("#manifest").fill('[{"url":"https://example.org/real-source-required.mp4","title":"Owned media","season":1,"episode":1}]')
                page.locator("#scan-manifest").click()
                wait_until(page,"() => document.querySelectorAll('.video-row').length===1")
                wait_until(page,"() => !document.getElementById('queue-selected').disabled")
                page.locator("#queue-selected").click()
                wait_until(page,"() => document.querySelectorAll('.job').length===1")
                page.locator("[data-action=pause]").click()
                wait_until(page,"() => document.querySelector('.badge').textContent==='paused'")
                page.locator("[data-action=resume]").click()
                wait_until(page,"() => document.querySelector('.badge').textContent==='queued'")
                with page.expect_download() as download:
                    page.locator("#download-report").click()
                assert download.value.suggested_filename=="reelforge-download-report.csv"
                page.locator("[data-view=ingest]").first.click()
                # Narrow layout must not overflow the viewport.
                page.set_viewport_size({"width":390,"height":844})
                assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
                page.locator('.nav[data-view="help"]').click()
                page.locator('.help-jumps [data-help="help-faq"]').click()
                assert page.locator("#faq-search").is_visible()
                assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
                page.locator('.nav[data-view="ingest"]').click()
                page.set_viewport_size({"width":1440,"height":1100})
                page.locator('[data-mode="records"]').click()
                page.locator("#preset").select_option("playlist")
                page.locator("#source-url").fill(f"http://127.0.0.1:{port}/fixture/index.json")
                page.locator("#records-path").fill("payload.videos")
                page.locator("#record-url").fill("media.url")
                page.locator("#record-title").fill("name")
                page.locator("#scan").click()
                wait_until(page,"() => document.querySelector('.video-title')?.textContent==='Example session'")
                references=root/"references.json"
                references.write_text(json.dumps({"name":"My records","records":[{"title":"Example session","year_start":1995,"year_end":1995,"url":"https://example.org/reference"}]}))
                page.locator(".reference-settings summary").click()
                page.locator("#reference-file").set_input_files(str(references))
                wait_until(page,"() => document.getElementById('reference-status').textContent.includes('My records')")
                page.locator("#date-research").click()
                wait_until(page,"() => document.getElementById('date-feedback').textContent.includes('completed')")
                wait_until(page,"() => document.querySelector('#results .date-badge')?.textContent.includes('documented')")
                page.locator("#reference-clear").click()
                wait_until(page,"() => document.getElementById('reference-status').textContent.includes('No reference library')")
                page.locator("#date-research").click()
                wait_until(page,"() => document.querySelector('#results .date-badge')?.textContent.includes('unknown')")
                page.locator("#date-demo").click()
                wait_until(page,"() => document.querySelectorAll('.video-row').length===6")
                page.locator("#date-research").click()
                wait_until(page,"() => document.getElementById('date-feedback').textContent.includes('completed')")
                wait_until(page,"() => document.getElementById('selected-count').textContent==='0 selected'")
                page.locator("#date-select").click()
                wait_until(page,"() => document.getElementById('selected-count').textContent==='2 selected'")
                assert page.locator(".video-row").count()==2
                page.locator("#date-confidence").select_option("likely")
                page.locator("#date-select").click()
                wait_until(page,"() => document.getElementById('selected-count').textContent==='3 selected'")
                page.locator("#date-view").select_option("outside")
                assert page.locator(".video-row").count()==1
                assert "New Edition" in page.locator(".video-title").inner_text()
                page.locator("#date-view").select_option("unknown")
                page.locator("[data-date]").first.click()
                page.locator("#date-review-start").fill("1993")
                page.locator("#date-review-end").fill("1993")
                page.locator("#date-review-confidence").select_option("documented")
                page.locator("#date-review-note").fill("Source matched to a dated archive during manual review.")
                page.locator("#date-save").click()
                wait_until(page,"() => document.getElementById('date-review-feedback').textContent.includes('saved')")
                page.locator("#date-close").click()
                page.locator("#date-view").select_option("inside")
                page.locator("#date-select").click()
                wait_until(page,"() => document.getElementById('selected-count').textContent==='4 selected'")
                with page.expect_download() as date_report:
                    page.locator("#date-export").click()
                assert date_report.value.suggested_filename=="reelforge-date-review.csv"
                # Rescanning unchanged source titles restores reviewed decisions.
                page.locator("#date-demo").click()
                wait_until(page,"() => document.getElementById('scan-feedback').textContent.includes('Sample metadata loaded')")
                page.locator("#date-view").select_option("any")
                wait_until(page,"() => document.querySelectorAll('.video-row').length===6")
                wait_until(page,"() => document.querySelectorAll('#results .date-reviewed').length===1")
                # Confidence totals include years outside the selected period.
                sample=[{"url":f"https://example.org/dated-{year}.mp4","title":f"Sample film {year}"}
                        for year in [2000,2001,2002,2003,2004,2005,2006,1999,2012]]
                page.locator("#manifest").fill(json.dumps(sample))
                page.locator("#date-start").fill("2000")
                page.locator("#date-end").fill("2009")
                page.locator("#scan-manifest").click()
                wait_until(page,"() => document.querySelectorAll('.video-row').length===9")
                page.locator("#date-research").click()
                wait_until(page,"() => document.getElementById('date-feedback').textContent.includes('completed')")
                wait_until(page,"() => !document.getElementById('date-select').disabled")
                assert page.locator('[data-date-view="likely"]').inner_text()=="9 likely"
                assert page.locator('[data-date-view="inside"]').inner_text()=="7 match selection rules"
                assert page.locator('[data-date-view="outside"]').inner_text()=="2 outside target period"
                page.locator("#date-select").click()
                wait_until(page,"() => document.getElementById('selected-count').textContent==='7 selected'")
                page.locator('[data-date-view="likely"]').click()
                assert page.locator(".video-row").count()==9
                assert page.locator("#date-view").input_value()=="likely"
                page.locator('[data-date-view="outside"]').click()
                assert page.locator(".video-title").all_text_contents()==["Sample film 1999","Sample film 2012"]
                assert page.locator("#results .date-period.outside").all_text_contents()==["Outside 2000–2009"]*2
                assert page.locator("#selected-count").inner_text()=="7 selected"
                page.locator('[data-date-view="inside"]').click()
                assert page.locator(".video-row").count()==7
                page.set_viewport_size({"width":390,"height":844})
                assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
                page.set_viewport_size({"width":1440,"height":1100})
                if os.environ.get("REELFORGE_QA_SCREENSHOT"):
                    page.locator('.nav[data-view="help"]').click()
                    page.locator('.help-jumps [data-help="help-start"]').click()
                    page.screenshot(path=os.environ["REELFORGE_QA_SCREENSHOT"],full_page=True)
                assert not errors,errors
                browser.close()
                print("Browser smoke passed: help navigation, contextual links, searchable FAQ, keyboard/mobile access, preserved selection, generic ingestion, references, queue controls, date research, saved reviews, and exports; no JavaScript errors.")
        finally:
            server.should_exit=True
            thread.join(timeout=5)

if __name__=="__main__":
    main()

