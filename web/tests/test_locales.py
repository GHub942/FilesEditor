import json
import re
import unittest
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1]


def flatten_translations(value, prefix=""):
    flattened = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.update(flatten_translations(item, path))
        else:
            flattened[path] = item
    return flattened


class LocaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.locales = {}
        for language in ("en", "fr"):
            locale_path = WEB_ROOT / "locales" / f"{language}.json"
            with locale_path.open(encoding="utf-8") as locale_file:
                cls.locales[language] = flatten_translations(json.load(locale_file))

    def test_supported_locales_have_the_same_translation_keys(self):
        self.assertEqual(set(self.locales["en"]), set(self.locales["fr"]))

    def test_html_translation_keys_exist_in_every_locale(self):
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        used_keys = set(re.findall(r'data-i18n(?:-[\w-]+)?="([^"]+)"', html))
        for language, translations in self.locales.items():
            with self.subTest(language=language):
                self.assertLessEqual(used_keys, set(translations))

    def test_javascript_translation_keys_exist_in_every_locale(self):
        script = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        used_keys = set(re.findall(r'translate\("([^"]+)"', script))
        for language, translations in self.locales.items():
            with self.subTest(language=language):
                self.assertLessEqual(used_keys, set(translations))

    def test_javascript_error_translation_targets_exist_in_every_locale(self):
        script = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        used_keys = set(re.findall(r'"(errors\.[\w.]+)"', script))
        for language, translations in self.locales.items():
            with self.subTest(language=language):
                self.assertLessEqual(used_keys, set(translations))

    def test_interpolation_parameters_match_between_locales(self):
        placeholders = {
            language: {
                key: set(re.findall(r"\{(\w+)\}", value))
                for key, value in translations.items()
            }
            for language, translations in self.locales.items()
        }
        self.assertEqual(placeholders["en"], placeholders["fr"])


if __name__ == "__main__":
    unittest.main()
