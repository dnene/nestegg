from nestegg import NesteggException
from nestegg.config import Repository
import unittest

class TestPath(unittest.TestCase):
    def test_default_constructor(self):
        with self.assertRaises(NesteggException) as ne :
            Repository(None)
        self.assertEqual("name is mandatory for a repository",
                          ne.exception.args[0])
    
    def test_constructor_with_only_name(self):
        with self.assertRaises(NesteggException) as ne :
            Repository(None, name="foobar")
        self.assertEqual("vcs type must be git or hg",
                          ne.exception.args[0])
    
    def test_constructor_with_name_and_vcs(self):
        with self.assertRaises(NesteggException) as ne :
            Repository(None, name="foobar", vcs="git")
        self.assertEqual("vcs url must be provided",
                          ne.exception.args[0])
    
    def test_constructor_with_name_vcs_and_type(self):
        r = Repository("parent",name="name", vcs="git", url="url")
        self.assertEqual("parent", r.parent)
        self.assertEqual("name", r.name)
        self.assertEqual("git", r.vcs)
        self.assertEqual("url", r.url)
        self.assertFalse(r.private)
        self.assertEqual([],r.releases)
        self.assertEqual([], r.branches)
        
    def test_constructor_with_all_parameters(self):
        r = Repository("parent",name="name", vcs="git", url="url", 
                       private=True, releases=[{"version": "version1"}], 
                       branches=[{"name": "name1"}])
        self.assertEqual("parent", r.parent)
        self.assertEqual("name", r.name)
        self.assertEqual("git", r.vcs)
        self.assertEqual("url", r.url)
        self.assertTrue(r.private)
        self.assertEqual(1,len(r.releases))
        rel = r.releases[0]
        self.assertEqual(r, rel.parent)
        self.assertEqual("version1", rel.version)
        self.assertEqual(1,len(r.branches))
        br = r.branches[0]
        self.assertEqual(r, br.parent)
        self.assertEqual("name1", br.name)
        
