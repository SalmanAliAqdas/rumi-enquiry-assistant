"""Optional real-browser check: python -m scripts.browser_smoke.

Uses an isolated temporary SQLite database, fictional data, and a random password.
Requires the browser extra and an installed Google Chrome browser.
"""

import secrets
import socket
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright
from sqlmodel import Session
from uvicorn import Config, Server

from app.auth import password_hasher
from app.config import Settings
from app.db import init_db, make_engine
from app.main import create_app
from app.models import Admin


def main():
    screenshots = Path("artifacts")
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rumi-browser-") as temporary:
        database_url = f"sqlite:///{Path(temporary) / 'smoke.db'}"
        engine = make_engine(database_url)
        init_db(engine)
        password = secrets.token_urlsafe(24)
        with Session(engine) as db:
            db.add(
                Admin(username="fictional-reviewer", password_hash=password_hasher.hash(password))
            )
            db.commit()
        engine.dispose()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        address = f"http://127.0.0.1:{port}"
        app = create_app(Settings(database_url=database_url, cookie_secure=False, _env_file=None))
        server = Server(
            Config(app, host="127.0.0.1", port=port, access_log=False, log_level="error")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                try:
                    with urlopen(address, timeout=1) as response:
                        assert response.status == 200
                    break
                except URLError:
                    if not thread.is_alive():
                        raise RuntimeError("Smoke server exited before startup") from None
                    time.sleep(0.1)
            else:
                raise RuntimeError("Smoke server did not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1050})
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(address)
                page.screenshot(path=str(screenshots / "form-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(screenshots / "form-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.get_by_label("Your name").fill("Alex Example")
                page.get_by_label("Email address").fill("alex@example.com")
                page.get_by_label("What would you like to build?").fill(
                    "We need a website for a fictional learning project."
                )
                page.get_by_role("button", name="Submit enquiry").click()
                expect(page.get_by_text("Your enquiry is saved.")).to_be_visible()
                assert page.locator("#receipt-reference").inner_text().startswith("REA-")
                page.goto(address + "/admin")
                expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
                page.get_by_label("Username", exact=True).fill("fictional-reviewer")
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_role("button", name="Sign in", exact=True).click()
                expect(page.get_by_role("heading", name="Enquiry inbox")).to_be_visible()
                # Ensure screenshots do not contain credentials or a prefilled password.
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.screenshot(path=str(screenshots / "dashboard-desktop.png"), full_page=True)
                page.get_by_label("Category", exact=True).select_option("Website")
                page.get_by_role("button", name="Apply filters").click()
                expect(page.get_by_text("Alex Example", exact=True)).to_be_visible()
                page.get_by_role("link", name="Open enquiry from Alex Example").click()
                page.get_by_label("Reply draft", exact=True).fill(
                    "Fictional revised draft. Please clarify your goals."
                )
                page.get_by_label("Workflow status").select_option("Reviewed")
                page.get_by_role("button", name="Save changes").click()
                expect(page.get_by_role("status")).to_contain_text("Changes saved")
                page.reload()
                expect(page.get_by_label("Workflow status")).to_have_value("Reviewed")
                page.screenshot(path=str(screenshots / "detail-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(screenshots / "detail-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.get_by_role("button", name="Sign out").click()
                expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
                assert page.request.get(address + "/api/admin/enquiries").status == 401
                assert not errors, errors
                browser.close()
                print(
                    "Browser smoke passed: mobile submission, login, filtering, draft edit, "
                    "persistence, logout; no JavaScript errors."
                )
                print("Fictional-data screenshots saved in ignored artifacts/.")
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Smoke server did not stop")


if __name__ == "__main__":
    main()
