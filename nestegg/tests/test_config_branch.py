from nestegg import NesteggException
from nestegg.config import Branch
import unittest

class TestPath(unittest.TestCase):
    def test_default_constructor(self):
        with self.assertRaises(NesteggException) as ne :
            Branch(None)
        self.assertEquals("name mandatory for a branch",
                          ne.exception.args[0])
    
    def test_constructor_with_name(self):
        b = Branch("parent",name="name")
        self.assertEquals("parent", b.parent)
        self.assertEquals("name", b.name)
        self.assertEquals({}, b.schedule)
        self.assertEquals("python", b.python)
        self.assertEquals(None, b.dist_file)

    def test_constructor_with_all_params(self):
        b = Branch("parent",name="name", python="python99", schedule="foo",
                    dist_file="dist_file")
        self.assertEquals("parent", b.parent)
        self.assertEquals("foo", b.schedule)
        self.assertEquals("python99", b.python)
        self.assertEquals("dist_file", b.dist_file)

