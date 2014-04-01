from nestegg.pypi import get_real_pkg_name, get_package_details
import unittest


class TestPypi(unittest.TestCase):
    def test_get_real_packagename(self):
        self.assertEqual("Jinja2", get_real_pkg_name("jinja2"))
        
    def test_get_package_details(self):
        get_package_details("jinja2")
        get_package_details("mysql-connector-python")