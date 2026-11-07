import os
import sys
import threading
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import FilesEditorHandler


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

    def test_preview_filter_page_size_and_ephemeral_presets(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index in range(63):
                Path(temporary, f"sample-{index:03}.txt").write_text("sample", encoding="utf-8")
            Path(temporary, "skip.bak").write_text("ignored by default", encoding="utf-8")
            Path(temporary, "skip.skip").write_text("ignored by preference", encoding="utf-8")
            nested = Path(temporary, "ignored-nested")
            nested.mkdir()
            (nested / "nested.txt").write_text("ignored by preference", encoding="utf-8")

            self.page.goto(f"{self.base_url}/tools/01")
            self.page.wait_for_load_state("networkidle")
            self.page.locator('[data-page="settings"]').click()
            self.page.locator("#defaultExcludedExtensions").fill(".tmp, .bak, .skip")
            excluded_dirs = self.page.locator("#defaultExcludedDirs")
            excluded_dirs.fill(f"{excluded_dirs.input_value()}, ignored-nested")
            self.page.locator("#closeSettingsButton").click()
            self.page.locator("#folderPath").fill(temporary)
            self.page.locator("#globalPrefix").fill("batch")
            self.page.locator(".switch-row").click()
            expect(self.page.locator("#recursive")).to_be_checked()
            self.page.locator("#previewButton").click()
            expect(self.page.locator("#previewRows tr")).to_have_count(50)
            expect(self.page.locator("#previewPageIndicator")).to_have_text("Page 1 of 2")

            self.page.locator("#previewSearch").fill("sample-062.txt")
            expect(self.page.locator("#previewRows tr")).to_have_count(1)
            expect(self.page.locator("#previewFilterCount")).to_have_text("1 of 63 changes shown")

            self.page.locator("#presetName").fill("Work batch")
            self.page.locator("#savePresetButton").click()
            expect(self.page.locator("#presetSelect")).to_have_value("Work batch")
            self.assertEqual(self.page.evaluate("localStorage.length"), 0)
            self.page.reload()
            self.page.wait_for_load_state("networkidle")
            self.assertEqual(self.page.locator("#presetSelect option").count(), 1)

            self.page.locator('[data-page="settings"]').click()
            self.page.locator("#pageSizeSelect").select_option("100")
            self.page.locator("#themeSelect").select_option("dark")
            self.page.locator("#defaultExcludedExtensions").fill(".tmp, .bak, .skip")
            self.assertEqual(self.page.locator("body").get_attribute("data-theme"), "dark")
            self.page.locator("#forgetPreferences").uncheck()
            self.page.locator("#closeSettingsButton").click()
            self.page.locator("#presetName").fill("Remember this")
            self.page.locator("#savePresetButton").click()
            self.page.reload()
            self.page.wait_for_load_state("networkidle")
            expect(self.page.locator("#presetSelect option")).to_have_count(2)
            expect(self.page.locator("#pageSizeSelect")).to_have_value("100")
            expect(self.page.locator("#themeSelect")).to_have_value("dark")
            expect(self.page.locator("#forgetPreferences")).not_to_be_checked()
            self.page.locator("#folderPath").fill(temporary)
            self.page.locator("#previewButton").click()
            expect(self.page.locator("#previewRows tr")).to_have_count(63)
            expect(self.page.locator("#previewPagination")).to_be_hidden()

    def test_operation_history_restores_files_through_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = Path(temporary, "photo.jpg")
            original.write_text("photo", encoding="utf-8")
            self.page.goto(f"{self.base_url}/tools/01")
            self.page.wait_for_load_state("networkidle")
            dialogs = []

            def handle_dialog(dialog):
                dialogs.append(dialog.message)
                if "full-copy and ZIP" in dialog.message:
                    dialog.dismiss()
                else:
                    dialog.accept()

            self.page.on("dialog", handle_dialog)
            self.page.locator("#folderPath").fill(temporary)
            self.page.locator("#globalPrefix").fill("batch")
            self.page.locator("#backupLog").uncheck()
            self.page.locator("#previewButton").click()
            expect(self.page.locator("#previewRows tr")).to_have_count(1)
            self.page.locator("#applyButton").click()
            renamed = Path(temporary, "batch__IMG_001.jpg")
            expect(self.page.locator("#toast")).to_contain_text("updated")
            self.assertTrue(renamed.exists())
            expect(self.page.locator(".history-entry")).to_have_count(1)

            self.page.locator(".history-entry .secondary-button").click()
            expect(self.page.locator("#previewRows tr")).to_have_count(1)
            self.page.locator("#applyButton").click()
            expect(self.page.locator("#toast")).to_contain_text("restored")
            self.assertTrue(original.exists())
            self.assertFalse(renamed.exists())
            expect(self.page.locator(".history-entry")).to_have_count(1)
            self.assertEqual(sum("full-copy and ZIP" in message for message in dialogs), 2)
