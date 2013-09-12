from nestegg import NesteggException
from nestegg.config import Release, Repository
import unittest

class TestPath(unittest.TestCase):
    def setUp(self):
        self.repo = Repository(None, vcs="git", 
                url="git@foo.bar:baz/buzz", name="foobar")

    def test_default_constructor(self):
        with self.assertRaises(NesteggException) as ne :
            Release(self.repo)
        self.assertEqual("version mandatory for a release",
                          ne.exception.args[0])
    
    def test_constructor_with_version(self):
        r = Release(self.repo, version="version")
        self.assertEqual(self.repo, r.parent)
        self.assertEqual("version", r.version)
        self.assertEqual("version", r.tag)
        self.assertEqual("python", r.python)
        self.assertEqual(None, r.dist_file)

    def test_constructor_with_all_params(self):
        r = Release(self.repo,version="version", tag="tag", python="python99",
                    dist_file="dist_file")
        self.assertEqual(self.repo, r.parent)
        self.assertEqual("version", r.version)
        self.assertEqual("tag", r.tag)
        self.assertEqual("python99", r.python)
        self.assertEqual("dist_file", r.dist_file)

