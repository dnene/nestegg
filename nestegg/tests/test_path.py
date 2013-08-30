from nestegg import NesteggException
from nestegg.path import Path
import os.path
import unittest

class TestPath(unittest.TestCase):
    def setUp(self):
        self.home = Path("~")
        self.homedir = os.path.expanduser("~")
        self.etc = Path("/etc")
    
    def test_constructor_simple(self):
        self.assertEqual(self.etc.p,"/etc")
    
    def test_constructor_expanded(self):
        self.assertEqual(os.path.expanduser("~") + "/foo", self.home.foo.p)
    
    def test_dereference_operator(self):
        self.assertEqual(self.homedir, +(self.home))
    
    def test_path_building_with_attr(self):
        self.assertEqual(self.homedir + "/projects", self.home.projects.p)
        
    def test_path_building_with_item(self):
        self.assertEqual(self.homedir + "/projects", self.home["projects"].p)
        
    def test_invalid_func_invocation(self):
        with self.assertRaises(NesteggException) as ne :
            self.home.do_invalid_operation()
        self.assertEqual("Invalid method do_invalid_operation on path",
                         ne.exception.args[0])
    
    def test_os_invocation(self):
        files = self.home.listdir()
        self.assertTrue(len(files) > 0)
        
    def test_opath_invocation(self):
        self.assertTrue(self.home.exists())
        self.assertFalse(Path("/sdfklj/sdlfkjsdkf/sdfkljsdf").exists())