import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from WEB.app import FilesEditorHandler


class WebRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FilesEditorHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join()

    def test_root_redirects_to_home(self):
        connection = HTTPConnection("127.0.0.1", self.server.server_port)
        self.addCleanup(connection.close)
        connection.request("GET", "/")
        response = connection.getresponse()
        self.assertEqual(response.status, 302)
        self.assertEqual(response.getheader("Location"), "/home")
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        response.read()

    def test_sidebar_has_adjacent_icon_only_home_and_settings_controls(self):
        response = urlopen(f"{self.base_url}/tools/01")
        self.addCleanup(response.close)
        body = response.read().decode("utf-8")
        home_position = body.index('class="sidebar-quick-nav"')
        settings_position = body.index('data-page="settings"', home_position)
        tools_position = body.index('class="tool-nav"', home_position)
        self.assertLess(home_position, settings_position)
        self.assertLess(settings_position, tools_position)
        self.assertIn('data-i18n-aria-label="app.home"', body[home_position:settings_position])

    def test_root_redirect_preserves_settings_query(self):
        response = urlopen(f"{self.base_url}/?settings=true")
        self.addCleanup(response.close)
        self.assertEqual(response.geturl(), f"{self.base_url}/home?settings=true")

    def test_file_tools_have_direct_routes(self):
        for route in ("/tools/01", "/tools/02", "/tools/undo"):
            with self.subTest(route=route):
                response = urlopen(f"{self.base_url}{route}")
                self.addCleanup(response.close)
                self.assertEqual(response.status, 200)
                self.assertIn(b'id="workspaceView"', response.read())
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_settings_query_is_served_on_current_page(self):
        response = urlopen(f"{self.base_url}/tools/01?settings=true")
        self.addCleanup(response.close)
        self.assertEqual(response.status, 200)
        self.assertIn(b'id="settingsDialog"', response.read())

    # Verify both the HTTP status and the app-rendered body using a real local request.
    def test_unknown_route_returns_localized_application_404(self):
        try:
            response = urlopen(f"{self.base_url}/missing-page")
        except HTTPError as error:
            self.assertEqual(error.code, 404)
            content_type = error.headers.get_content_type()
            body = error.read()
            error.close()
        else:
            response.close()
            self.fail("An unknown route should return HTTP 404.")

        self.assertEqual(content_type, "text/html")
        self.assertIn(b'id="notFoundView"', body)
        self.assertIn(b'data-i18n="notFound.title"', body)


if __name__ == "__main__":
    unittest.main()
