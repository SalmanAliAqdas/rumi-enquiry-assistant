"""Optional Chrome check of fictional public UI; uses a temporary SQLite DB."""

import socket
import tempfile
import threading
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from uvicorn import Config, Server

from app.config import Settings
from app.main import create_app


def main():
    artifacts = Path("artifacts")
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary, socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.close()
        app = create_app(
            Settings(
                database_url=f"sqlite:///{Path(temporary) / 'demo.db'}",
                processor_mode="demo",
                gemini_api_key="",
                _env_file=None,
            )
        )
        server = Server(
            Config(app, host="127.0.0.1", port=port, access_log=False, log_level="error")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.1)
            assert server.started
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}/explore")
                expect(
                    page.get_by_role("heading", name="Explore the enquiry workflow.")
                ).to_be_visible()
                expect(page.get_by_role("button", name="Simulate this enquiry")).to_have_count(3)
                expect(
                    page.get_by_text("Live generation is disabled.", exact=False)
                ).to_be_visible()
                page.get_by_text("View saved example result").first.click()
                page.screenshot(path=str(artifacts / "explore-desktop.png"), full_page=True)
                page.get_by_role("button", name="Simulate this enquiry").first.click()
                expect(page.get_by_text("Simulated", exact=True)).to_be_visible()
                expect(
                    page.get_by_role("heading", name="Draft · manual review required")
                ).to_be_visible()
                assert (
                    page.request.get(f"http://127.0.0.1:{port}/api/admin/enquiries").status == 401
                )
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(
                    path=str(artifacts / "explore-simulated-mobile.png"), full_page=True
                )
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                assert not errors, errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
    print("Explore browser check passed: fixtures, simulation, mobile layout, private API guard.")


if __name__ == "__main__":
    main()
