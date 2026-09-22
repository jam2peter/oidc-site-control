import os
import pathlib
import tempfile
import unittest

import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from site_control import MARKER, build_bundle, load_config, safe_rel


CFG={
    "endpoint":"https://deploy.example.com/control/",
    "audience":"https://deploy.example.com/control/",
    "oidc_header":"X-Site-Control-GitHub-OIDC",
    "allowed_roots":["apps","projects"],
    "limits":{"max_files":100,"max_bytes":1024*1024},
}


class Tests(unittest.TestCase):
    def test_example_config(self):
        cfg=load_config(str(ROOT/"site-control.example.json"))
        self.assertEqual(cfg["allowed_roots"],["apps","projects"])

    def test_bundle_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)
            (p/"b.txt").write_text("B")
            (p/"a.txt").write_text("A")
            a=build_bundle(td,"apps/demo","a"*40,CFG)
            b=build_bundle(td,"apps/demo","a"*40,CFG)
            self.assertEqual(a["manifest_sha256"],b["manifest_sha256"])
            self.assertEqual(a["idempotency_key"],b["idempotency_key"])
            self.assertEqual(sorted(a["files"]),["a.txt","b.txt"])

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)
            (p/"real").write_text("x")
            os.symlink(p/"real",p/"link")
            with self.assertRaises(SystemExit):
                build_bundle(td,"apps/demo","b"*40,CFG)

    def test_reserved_marker_rejected(self):
        self.assertFalse(safe_rel(MARKER))

    def test_unknown_root_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            pathlib.Path(td,"index.html").write_text("x")
            with self.assertRaises(SystemExit):
                build_bundle(td,"other/demo","c"*40,CFG)


if __name__=="__main__":
    unittest.main()
