from nestegg import NesteggException
from nestegg.config import Release
import unittest

class TestPath(unittest.TestCase):
    def test_default_constructor(self):
        with self.assertRaises(NesteggException) as ne :
            Release(None)
        self.assertEqual("version mandatory for a release",
                          ne.exception.args[0])
    
    def test_constructor_with_version(self):
        r = Release("parent",version="version")
        self.assertEqual("parent", r.parent)
        self.assertEqual("version", r.version)
        self.assertEqual("version", r.tag)
        self.assertEqual("python", r.python)
        self.assertEqual(None, r.dist_file)

    def test_constructor_with_all_params(self):
        r = Release("parent",version="version", tag="tag", python="python99",
                    dist_file="dist_file")
        self.assertEqual("parent", r.parent)
        self.assertEqual("version", r.version)
        self.assertEqual("tag", r.tag)
        self.assertEqual("python99", r.python)
        self.assertEqual("dist_file", r.dist_file)

