from nestegg import NesteggException
from requests import get, head

from xmlrpc.client import ServerProxy, Transport

pypi_client = ServerProxy("https://pypi.python.org/pypi", Transport())

def get_real_pkg_name(pkg_name):
    r = head('https://pypi.python.org/simple/{0}/'.format(pkg_name))
    if r.status_code == 200 :
        return pkg_name
    if 300 <= r.status_code <= 399 :
        location = r.headers["location"]
        if location.startswith("/simple/") :
            return location.split("/")[-1]
        else :
            raise NesteggException(
                    "Unexpected redirect from pypi: {}".format(location))
    raise NesteggException(
        "Unable to get real package name for {} from pypi".format(pkg_name))
                
def get_package_details(pkg_name):
    real_pkg_name = get_real_pkg_name(pkg_name)
    releases = pypi_client.package_releases(real_pkg_name, True)
    print(releases)
    for release in releases :
        urls = pypi_client.release_urls(real_pkg_name, release)
        print(release, urls)
    
#     r = get("https://pypi.python.org/simple/{0}".format(real_pkg_name))
#     if r.status_code == 200 :
#         from bs4 import BeautifulSoup
#         print(r.text)
#         print("====================")
#         doc = BeautifulSoup(r.text)
#         links = doc.find_all("a")
#         for link in links :
#             print(link)
#         
#     else :
#         raise NesteggException(
#             "Unable to get package details for {}".format(real_pkg_name))
    
    
    