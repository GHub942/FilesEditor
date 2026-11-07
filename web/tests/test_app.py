import threading
import unittest
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
