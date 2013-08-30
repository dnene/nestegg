from nestegg import NesteggException
from nestegg.config import Release
import unittest

class TestPath(unittest.TestCase):
    def test_default_constructor(self):
        with self.assertRaises(NesteggException) as ne :
            Release(None)
        self.assertEquals("version mandatory for a release",
                          ne.exception.args[0])
    
    def test_constructor_with_version(self):
        r = Release("parent",version="version")
        self.assertEquals("parent", r.parent)
        self.assertEquals("version", r.version)
        self.assertEquals("version", r.tag)
        self.assertEquals("python", r.python)
        self.assertEquals(None, r.dist_file)

    def test_constructor_with_all_params(self):
        r = Release("parent",version="version", tag="tag", python="python99",
                    dist_file="dist_file")
        self.assertEquals("parent", r.parent)
        self.assertEquals("version", r.version)
        self.assertEquals("tag", r.tag)
        self.assertEquals("python99", r.python)
        self.assertEquals("dist_file", r.dist_file)

