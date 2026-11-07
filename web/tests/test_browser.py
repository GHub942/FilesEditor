import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from WEB.app import FilesEditorHandler


class BrowserVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FilesEditorHandler)
        cls.addClassCleanup(cls.server.server_close)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.addClassCleanup(cls._stop_server)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch()
        cls.addClassCleanup(cls.browser.close)

    @classmethod
    def _stop_server(cls):
        cls.server.shutdown()
        cls.server_thread.join()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 1000})
        self.page.goto(f"{self.base_url}/home")
        self.page.wait_for_load_state("networkidle")

    def tearDown(self):
        self.page.close()

    def save_screenshot(self, name):
        output_dir = Path(os.environ.get("PLAYWRIGHT_SCREENSHOT_DIR", "web-test-artifacts"))
        output_dir.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(output_dir / name), full_page=True)

    def test_desktop_navigation_selection_tooltips_and_keyboard_focus(self):
        home = self.page.locator('.sidebar-quick-nav a[href="/home"]')
        settings = self.page.locator('[data-page="settings"]')
        self.assertEqual(home.get_attribute("aria-current"), "page")
        self.assertIn("active", home.get_attribute("class"))
        self.assertEqual(home.get_attribute("title"), "Files Editor home")
        self.assertEqual(settings.get_attribute("title"), "Settings")
        inactive_settings_color = settings.evaluate(
            "(element) => getComputedStyle(element).backgroundColor"
        )
        self.assertNotEqual(
            home.evaluate("(element) => getComputedStyle(element).backgroundColor"),
            inactive_settings_color,
        )

        self.page.keyboard.press("Tab")
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.getAttribute('href')"), "/home")
        self.assertNotEqual(home.evaluate("(element) => getComputedStyle(element).outlineStyle"), "none")

        settings.click()
        self.assertTrue(self.page.locator("#settingsDialog").is_visible())
        self.assertEqual(settings.get_attribute("aria-pressed"), "true")
        self.assertIn("active", settings.get_attribute("class"))
        expect(settings).to_have_css("background-color", "rgb(35, 66, 63)")
        self.assertIn("settings=true", self.page.url)
        self.save_screenshot("desktop-settings.png")
        self.page.locator("#languageSelect").select_option("fr")
        expect(home).to_have_attribute("title", "Accueil Files Editor")
        expect(settings).to_have_attribute("title", "Paramètres")

        self.page.keyboard.press("Escape")
        expect(self.page.locator("#settingsDialog")).to_be_hidden()
        expect(settings).to_have_attribute("aria-pressed", "false")
        expect(self.page).not_to_have_url("**settings=true*")

    def test_mobile_layout_and_tool_selection(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.goto(f"{self.base_url}/tools/02")

        home = self.page.locator('.sidebar-quick-nav a[href="/home"]')
        settings = self.page.locator('[data-page="settings"]')
        selected_tool = self.page.locator('.nav-item[data-mode="extensions"]')
        widths = self.page.locator(".icon-nav-button").evaluate_all(
            "(buttons) => buttons.map((button) => button.getBoundingClientRect().width)"
        )
        self.assertAlmostEqual(widths[0], widths[1], delta=1)
        self.assertEqual(selected_tool.get_attribute("aria-current"), "page")
        self.assertNotEqual(
            selected_tool.evaluate("(element) => getComputedStyle(element).backgroundColor"),
            self.page.locator('.nav-item[data-mode="rename"]').evaluate(
                "(element) => getComputedStyle(element).backgroundColor"
            ),
        )
        self.assertEqual(home.get_attribute("aria-current"), "false")
        self.assertEqual(settings.get_attribute("aria-pressed"), "false")
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth"),
        )
        self.assertTrue(self.page.locator("#pageHeading").is_visible())
        self.save_screenshot("mobile-extension-editor.png")
