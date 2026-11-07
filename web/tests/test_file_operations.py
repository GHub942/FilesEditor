import tempfile
import unittest
from pathlib import Path

from web.file_operations import OperationError, apply_preview, create_preview


class FileOperationTests(unittest.TestCase):
    def test_rename_apply_and_undo_preserve_file_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Photos"
            root.mkdir()
            (root / "large.jpg").write_bytes(b"large")
            (root / "small.jpg").write_bytes(b"x")

            preview = create_preview("rename", {
                "folder": str(root),
                "globalPrefix": "",
                "separator": "__",
                "padding": 2,
                "categories": ["IMG"],
                "categoryPrefixes": {},
            })
            self.assertEqual(preview.entries[0]["old"].name, "small.jpg")
            self.assertEqual(preview.entries[0]["new"].name, "Photos__IMG_01.jpg")

            apply_preview(preview, {})
            renamed_path = root / "Photos__IMG_01.jpg"
            self.assertEqual(renamed_path.read_bytes(), b"x")

            undo = create_preview("undo", {
                "folder": str(root),
                "log": preview.log_data,
            })
            self.assertEqual(len(undo.entries), 2)
            apply_preview(undo, {})
            self.assertEqual((root / "small.jpg").read_bytes(), b"x")
            self.assertEqual((root / "large.jpg").read_bytes(), b"large")

    def test_extension_change_avoids_existing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "photo.jpg").write_bytes(b"image bytes")
            (root / "photo.png").write_bytes(b"existing image")

            preview = create_preview("extensions", {
                "folder": str(root),
                "targets": {"IMG": ".png"},
            })
            self.assertEqual(len(preview.entries), 1)
            self.assertEqual(preview.entries[0]["new"].name, "photo_1.png")

            apply_preview(preview, {})
            self.assertEqual((root / "photo_1.png").read_bytes(), b"image bytes")
            self.assertEqual((root / "photo.png").read_bytes(), b"existing image")

    def test_recursive_scan_excludes_development_folders_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "node_modules").mkdir()
            (root / "nested" / "inside.txt").write_text("inside", encoding="utf-8")
            (root / "node_modules" / "ignored.txt").write_text("ignored", encoding="utf-8")

            preview = create_preview("rename", {
                "folder": str(root),
                "recursive": True,
                "globalPrefix": "batch",
                "separator": "__",
                "padding": 1,
                "categories": ["DOC"],
                "categoryPrefixes": {},
            })
            self.assertEqual(len(preview.entries), 1)
            self.assertEqual(preview.entries[0]["old"].relative_to(root).as_posix(), "nested/inside.txt")

    def test_apply_refuses_to_overwrite_destination_created_after_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Images"
            root.mkdir()
            (root / "photo.jpg").write_bytes(b"original")

            preview = create_preview("rename", {
                "folder": str(root),
                "globalPrefix": "Images",
                "separator": "__",
                "padding": 1,
                "categories": ["IMG"],
                "categoryPrefixes": {},
            })
            destination = root / "Images__IMG_1.jpg"
            destination.write_bytes(b"keep")

            with self.assertRaisesRegex(OperationError, "destination already exists"):
                apply_preview(preview, {})
            self.assertEqual((root / "photo.jpg").read_bytes(), b"original")
            self.assertEqual(destination.read_bytes(), b"keep")

    def test_undo_rejects_paths_outside_the_selected_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "safe"
            root.mkdir()
            log = {
                "target_directory": str(root),
                "renamed_files": [{
                    "original_path": str(Path(temporary) / "outside.txt"),
                    "new_path": str(root / "inside.txt"),
                }],
            }
            with self.assertRaisesRegex(OperationError, "outside the selected folder"):
                create_preview("undo", {"folder": str(root), "log": log})


if __name__ == "__main__":
    unittest.main()
