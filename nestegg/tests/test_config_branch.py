#from nestegg import NesteggException
#from nestegg.config import Branch
#import unittest

#class TestBranch(unittest.TestCase):
#    def test_default_constructor(self):
#        with self.assertRaises(NesteggException) as ne :
#            Branch(None)
#        self.assertEqual("name mandatory for a branch",
#                          ne.exception.args[0])
#    
#    def test_constructor_with_name(self):
#        b = Branch("parent",name="name")
#        self.assertEqual("parent", b.parent)
#        self.assertEqual("name", b.name)
#        self.assertEqual({}, b.schedule)
#        self.assertEqual("python", b.python)
#        self.assertEqual(None, b.dist_file)
#
#    def test_constructor_with_all_params(self):
#        b = Branch("parent",name="name", python="python99", schedule="foo",
#                    dist_file="dist_file")
#        self.assertEqual("parent", b.parent)
#        self.assertEqual("foo", b.schedule)
#        self.assertEqual("python99", b.python)
#        self.assertEqual("dist_file", b.dist_file)

