"""Drive the running prototype in a headless browser and screenshot every section.

Usage:  python3 app.py &   then   python3 verify_ui.py
Requires: pip install playwright && python3 -m playwright install chromium
Fails loudly on any console error, so a broken view cannot pass unnoticed.
"""
import asyncio
from playwright.async_api import async_playwright
import os
S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shots", "")
os.makedirs(S, exist_ok=True)
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width":1560,"height":1000})
        errs=[]
        pg.on("console", lambda m: errs.append((m.type,m.text)) if m.type=="error" else None)
        pg.on("pageerror", lambda e: errs.append(("pageerror",str(e))))
        await pg.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await pg.wait_for_timeout(800)
        await pg.screenshot(path=S+"f_dashboard.png", full_page=True)
        # ops on collapsed
        await pg.evaluate("location.hash='#/ops'"); await pg.wait_for_timeout(600)
        await pg.select_option("#ops-bid","SN-1147"); await pg.wait_for_timeout(400)
        await pg.click("#btn-run2"); await pg.wait_for_timeout(2200)
        await pg.screenshot(path=S+"f_ops.png", full_page=True)
        # preplan
        await pg.select_option("#ops-bid","VK-0204"); await pg.wait_for_timeout(400)
        await pg.click("#btn-run2"); await pg.wait_for_timeout(2200)
        await pg.screenshot(path=S+"f_preplan.png", full_page=True)
        # one team -> shortfall
        await pg.evaluate("location.hash='#/tasking'"); await pg.wait_for_timeout(900)
        await pg.select_option("#ops-bid","SN-1147") if False else None
        await pg.evaluate("location.hash='#/ops'"); await pg.wait_for_timeout(400)
        await pg.select_option("#ops-bid","SN-1147"); await pg.wait_for_timeout(300)
        await pg.evaluate("""() => { const s=document.querySelector('#ops-teams'); s.value=1; s.dispatchEvent(new Event('input')); }""")
        await pg.wait_for_timeout(200)
        await pg.evaluate("""() => { const s=document.querySelector('#ops-horizon'); s.value=12; s.dispatchEvent(new Event('input')); }""")
        await pg.click("#btn-run2"); await pg.wait_for_timeout(2200)
        await pg.evaluate("location.hash='#/tasking'"); await pg.wait_for_timeout(1200)
        await pg.screenshot(path=S+"f_tasking_short.png", full_page=True)
        await pg.evaluate("location.hash='#/accuracy'"); await pg.wait_for_timeout(1800)
        await pg.screenshot(path=S+"f_accuracy.png", full_page=True)
        await pg.evaluate("location.hash='#/queue'"); await pg.wait_for_timeout(700)
        await pg.screenshot(path=S+"f_queue.png", full_page=True)
        if errs:
            raise SystemExit("CONSOLE ERRORS: %s" % errs)
        print("no console errors · screenshots in", S)
        await b.close()
asyncio.run(main())
