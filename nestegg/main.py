import logging, os, shutil, sys, tempfile, os.path as opath, configparser
from bottle import run, abort, static_file, SimpleTemplate, default_app
from pkg_resources import Requirement
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
import logging.config
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def get_default_config_file():
    try :
        return next(filter(lambda f: opath.exists(f), 
                [opath.join(opath.expanduser('~'), 'nestegg.ini'),
                 opath.join(opath.dirname(opath.abspath(sys.argv[0])), 
                              '../etc/nestegg.ini'),
                 '/etc/nestegg.ini' ]))
    except StopIteration :
        return None

def get_app():
    app = default_app()
    app.config.update({
        "nestegg.eggs_dir": "{}/.nestegg/cache".format(
                                        opath.expanduser('~')),
        "nestegg.index_url": "http://pypi.python.org/simple",
        "nestegg.port": "7654", "nestegg.fresh": '0'})
    config_file = get_default_config_file()
    if config_file :
        config = configparser.ConfigParser() 
        with open(config_file,"r") as in_config :
            config.read_file(in_config)
            section = config['nestegg'] 
            for key in section :
                app.config["nestegg.{}".format(key)] = section[key]
                        
            
        logging.config.fileConfig(config_file)
    return app

class NesteggPackageIndex(PackageIndex):
    def __init__(self, fresh, *args, **kwargs):
        self.fresh = "fresh" == "1"
        super().__init__(*args,**kwargs)
    
    def process_index(self, url, page):
        if self.fresh: 
            del self.fetched_urls[url]
        super().process_index(url, page)

app = get_app()  
eggs_dir, index_url, fresh = [app.config.get("nestegg.{}".format(attr)) 
        for attr in ("eggs_dir", "index_url", "fresh")] 
os.makedirs(eggs_dir,0o755, exist_ok=True)
pkg_idx = NesteggPackageIndex(fresh, index_url)

with open("views/package.tpl", "r") as infile :
    pindex = SimpleTemplate(source=infile)
    
with open("views/all_packages.tpl", "r") as infile :
    gindex = SimpleTemplate(source=infile)

def _get_package_html(pkg_path, pkg_name, pkg_idx):
    os.makedirs(pkg_path, exist_ok=True)
    html_file = opath.join(pkg_path, "index.html")
    if pkg_idx.fresh or not opath.exists(html_file) :
        info = {"name" : pkg_name,"versions": 
            [egg_info(dist.location) for dist in pkg_idx[pkg_name]]}
        with open(html_file, "w") as outfile :
            outfile.write(pindex.render(**info))
    return (pkg_path, "index.html")
                
@app.route('/')
def get_root():
    if not opath.exists(opath.join(eggs_dir,"index.html")):
        log.debug("Updating base index")
        pkg_idx.scan_all()
        with open(opath.join(eggs_dir,"index.html"), "w") as h :
            h.write(gindex.render(pkgs=sorted(pkg_idx.package_pages)))
    return static_file("index.html", root=eggs_dir)    

@app.route('/<pkg_name>/')
def get_package(pkg_name):
    pkg_idx.find_packages(Requirement.parse(pkg_name))
    pkg_path = opath.join(eggs_dir, pkg_name)
    if not pkg_idx[pkg_name] :
        abort(404, "No such package {}".format(pkg_name))
    pkg_path, html_file = _get_package_html(pkg_path, pkg_name, pkg_idx)
    return static_file(html_file, root=pkg_path)  

@app.route('/<pkg_name>/<egg_name>')
def get_egg(pkg_name, egg_name):
    log.debug("Package: {} egg:{}".format(pkg_name, egg_name))
    pkg_dir = opath.join(eggs_dir, pkg_name)
    fpath = opath.join(eggs_dir, pkg_name, egg_name)
    if not opath.exists(fpath) :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
        for dist in pkg_idx[pkg_name] :
            if egg_info(dist.location)[0] == egg_name:
                log.debug("Fetch {}/{}".format(pkg_name,egg_name))
                tmp = tempfile.gettempdir()
                shutil.move(pkg_idx.download(dist.location, tmp), fpath)
                return static_file(egg_name, root=pkg_dir)
        abort(404,"No egg found for {} {}".format(pkg_name,egg_name))
    else :
        return static_file(egg_name, root=pkg_dir)

if __name__ == "__main__" :
    run(host='0.0.0.0', port = app.config.get("nestegg.port"))
