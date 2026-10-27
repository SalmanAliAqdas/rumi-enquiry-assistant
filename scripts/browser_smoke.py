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
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright
from sqlmodel import Session
from uvicorn import Config, Server

from app.auth import password_hasher
from app.config import Settings
from app.db import init_db, make_engine
from app.main import create_app
from app.models import Admin
from app.services import ProcessingFailure, ProcessingResult


class MockReviewProcessor:
    """An explicitly mocked provider, used only by this browser smoke script."""

    def __init__(self):
        self.calls = 0

    async def process(self, message):
        self.calls += 1
        if self.calls == 1:
            raise ProcessingFailure("quota")
        result = ProcessingResult(
            category="Website",
            summary="Fictional mocked website requirements.",
            reply_draft="Fictional approved fixture answer. Manual review required.",
            clarification_questions=["Who is the intended audience?"],
            faq_ids=["fictional-browser"],
            needs_clarification=True,
            review_reason="Fictional mocked response: audience needs clarification.",
        )
        result._faq_sources = [
            {
                "id": "fictional-browser",
                "question": "Fictional fixture?",
                "answer": "Fictional approved fixture answer.",
            }
        ]
        return result


def main():
    screenshots = Path("artifacts")
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rumi-browser-") as temporary:
        (Path(temporary) / "owner-faq.json").write_text("[]", encoding="utf-8")
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
        app = create_app(
            Settings(
                database_url=database_url,
                cookie_secure=False,
                processor_mode="demo",
                gemini_api_key="",
                faq_path=Path(temporary) / "owner-faq.json",
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
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1050},
                    permissions=["clipboard-read", "clipboard-write"],
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(address)
                page.keyboard.press("Tab")
                expect(page.get_by_role("link", name="Skip to content")).to_be_focused()
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
                page.screenshot(path=str(screenshots / "receipt-mobile.png"), full_page=True)
                page.goto(address + "/admin")
                expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
                assert page.get_by_label("Password", exact=True).input_value() == ""
                page.screenshot(path=str(screenshots / "login-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.screenshot(path=str(screenshots / "login-desktop.png"), full_page=True)
                page.get_by_label("Username", exact=True).fill("fictional-reviewer")
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_role("button", name="Sign in", exact=True).click()
                expect(page.get_by_role("heading", name="Enquiry inbox")).to_be_visible()
                expect(page.locator(".knowledge-notice")).to_contain_text("No approved FAQs")
                page.locator(".configuration-panel summary").click()
                expect(page.locator(".configuration-panel")).to_contain_text("Key configured")
                expect(page.locator(".configuration-panel")).to_contain_text("No")
                # Seed only isolated demo records so paging is exercised without
                # spending provider quota or touching normal application data.
                for index in range(6):
                    submitted = page.request.post(
                        address + "/api/enquiries",
                        data={
                            "name": f"Fictional Paging Example {index}",
                            "email": "paging@example.com",
                            "message": "A fictional website request for browser pagination checks.",
                            "submission_key": str(uuid4()),
                        },
                    )
                    assert submitted.status == 201
                page.goto(address + "/admin")
                page.get_by_label("Per page", exact=True).select_option("5")
                page.get_by_role("button", name="Apply filters").click()
                page.get_by_role("link", name="Next", exact=True).click()
                expect(page.locator(".pagination")).to_contain_text("Page 2")
                page.get_by_role("link", name="Previous", exact=True).click()
                expect(page.locator(".pagination")).to_contain_text("Page 1")
                # Ensure screenshots do not contain credentials or a prefilled password.
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.screenshot(path=str(screenshots / "dashboard-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(screenshots / "dashboard-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    page.evaluate(
                        """[...document.querySelectorAll('body *')].filter(e =>
                    e.getBoundingClientRect().right > innerWidth && !e.closest('.table-scroll'))
                    .map(e => [e.tagName, e.className, Math.round(e.getBoundingClientRect().right)])
                    .slice(0,20)"""
                    )
                )
                page.get_by_label("Search enquiries").fill("no-fictional-match")
                page.get_by_role("button", name="Apply filters").click()
                expect(page.locator(".empty")).to_contain_text("No enquiries on this page")
                page.screenshot(path=str(screenshots / "inbox-empty-mobile.png"), full_page=True)
                page.get_by_label("Search enquiries").fill("Alex Example")
                page.get_by_label("Category", exact=True).select_option("Website")
                page.get_by_role("button", name="Apply filters").click()
                expect(page.get_by_text("Alex Example", exact=True)).to_be_visible()
                page.get_by_role("link", name="Open enquiry from Alex Example").click()
                page.get_by_label("Reply draft", exact=True).fill(
                    "Fictional revised draft. Please clarify your goals."
                )
                page.get_by_label("Workflow status").select_option("Reviewed")
                page.get_by_role("button", name="Sign out").click()
                expect(page.locator("#draft-feedback")).to_contain_text(
                    "Save your draft changes before signing out"
                )
                expect(page.get_by_role("button", name="Sign out")).to_be_enabled()
                page.get_by_role("button", name="Save changes").click()
                expect(page.locator("#draft-feedback")).to_contain_text("Changes saved")
                expect(page.locator("#saved-workflow")).to_have_text("Reviewed")
                page.get_by_role("button", name="Copy current draft").click()
                expect(page.locator("#draft-feedback")).to_contain_text("Saved draft copied")
                assert (
                    page.evaluate("navigator.clipboard.readText()")
                    == "Fictional revised draft. Please clarify your goals."
                )
                page.reload()
                expect(page.get_by_label("Workflow status")).to_have_value("Reviewed")
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.screenshot(path=str(screenshots / "detail-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(screenshots / "detail-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                # Keep the full Phase 1 path above; exercise new failure/retry UI
                # with a scripted provider that cannot make network requests.
                app.state.processor = MockReviewProcessor()
                app.state.processing_mode = "gemini"
                app.state.processing_model = "mocked-browser-model"
                app.state.templates.env.globals["processing_label"] = (
                    "Mocked Gemini verification — no model connected."
                )
                page.goto(address)
                page.get_by_label("Your name").fill("Fictional Retry Example")
                page.get_by_label("Email address").fill("retry@example.com")
                page.get_by_label("What would you like to build?").fill(
                    "A fictional website enquiry for mocked processing review."
                )
                page.get_by_role("button", name="Submit enquiry").click()
                expect(page.get_by_text("Your enquiry is saved.")).to_be_visible()
                page.goto(address + "/admin")
                page.get_by_role("link", name="Open enquiry from Fictional Retry Example").click()
                expect(page.get_by_text("Processing needs attention", exact=True)).to_be_visible()
                page.screenshot(
                    path=str(screenshots / "processing-failure-mobile.png"), full_page=True
                )
                page.get_by_label("Reply draft", exact=True).fill(
                    "Human draft to preserve through the mocked retry."
                )
                page.get_by_label("Workflow status").select_option("Reviewed")
                page.get_by_role("button", name="Retry processing", exact=True).click()
                expect(page.locator("#processing-feedback")).to_contain_text(
                    "Save your draft changes"
                )
                assert app.state.processor.calls == 1
                page.get_by_role("button", name="Save changes").click()
                expect(page.locator("#draft-feedback")).to_contain_text("Changes saved")
                page.get_by_role("button", name="Retry processing", exact=True).click()
                expect(
                    page.get_by_role("heading", name="Review the processing candidate")
                ).to_be_visible()
                expect(page.get_by_label("Reply draft", exact=True)).to_have_value(
                    "Human draft to preserve through the mocked retry."
                )
                expect(page.get_by_label("Workflow status")).to_have_value("Reviewed")
                page.screenshot(path=str(screenshots / "candidate-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.screenshot(path=str(screenshots / "candidate-desktop.png"), full_page=True)
                page.get_by_role("button", name="Apply candidate to saved draft").click()
                expect(page.get_by_label("Reply draft", exact=True)).to_have_value(
                    "Fictional approved fixture answer. Manual review required."
                )
                expect(page.get_by_label("Workflow status")).to_have_value("Reviewed")
                assert app.state.processor.calls == 2
                page.get_by_role("button", name="Sign out").click()
                expect(page.get_by_role("heading", name="Welcome back.")).to_be_visible()
                assert page.request.get(address + "/api/admin/enquiries").status == 401
                assert not errors, errors
                browser.close()
                print(
                    "Browser smoke passed: mobile submission, login, filtering, draft edit, "
                    "search, pagination, empty state, clipboard, unsaved-edit guard, "
                    "persistence, mocked failure/retry/candidate application, logout; "
                    "no JavaScript errors."
                )
                print("Fictional-data screenshots saved in ignored artifacts/.")
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Smoke server did not stop")


if __name__ == "__main__":
    main()
