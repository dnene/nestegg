import os, shutil, sys, tempfile, os.path as opath 
from bottle import run, abort, static_file, SimpleTemplate, default_app
from pkg_resources import Requirement
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
from subprocess import call
from yaml import load, dump
from sh import git, hg, cd, cp
import logging.config
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def lookup_config_file(filename):
    try :
        return next(filter(lambda f: opath.exists(f), 
                [opath.join(opath.expanduser('~'), filename),
                 opath.join(opath.dirname(opath.abspath(sys.argv[0])), 
                              '../etc/{}'.format(filename)),
                 '/etc/{}'.format(filename) ]))
    except StopIteration :
        return None

class Config: pass
def get_config(data) :
    if isinstance(data, dict) :
        config = Config()
        for key, value in data.items() :
            setattr(config, key, get_config(value))
        return config
    elif isinstance(data, (list, tuple)) :
        return [get_config(item) for item in data]
    return data
    
def get_app():
    app = default_app()
    default_config = {
        "eggs_dir" : "{}/.nestegg/cache".format(opath.expanduser('~')),
        "index_url": "https://pypi.python.org/simple",
        "port": 7654,  "fresh": "0",
    }
    ini_file = lookup_config_file("nestegg.ini")
    if ini_file :
        logging.config.fileConfig(ini_file)
    config_file = lookup_config_file("nestegg.yml")
    if config_file :
        with open(config_file,"r") as in_config :
            config = get_config(load(in_config))
        for key, value in default_config.items() :
            if not hasattr(config.nestegg,key): 
                setattr(config.nestegg,key,value)
    else :
        config = get_config(default_config)
            
    app.config['config'] = config
    return app, config.nestegg

class NesteggPackageIndex(PackageIndex):
    def __init__(self, fresh, *args, **kwargs):
        self.fresh = "fresh" == "1"
        super().__init__(*args,**kwargs)
    
    def process_index(self, url, page):
        if self.fresh: 
            del self.fetched_urls[url]
        super().process_index(url, page)

app, ne_config = get_app()  

os.makedirs(ne_config.eggs_dir,0o755, exist_ok=True)
pkg_idx = NesteggPackageIndex(ne_config.fresh, ne_config.index_url)

def source_build_dir(eggs_dir,pkg) : 
    return opath.join(eggs_dir,"_source_builds", pkg.name)

def source_build_file(eggs_dir,pkg,dist_file) : 
    return opath.join(eggs_dir,"_source_builds", pkg.name, dist_file)

def check_source_builds(config):
    cwd = os.getcwd()
    eggs_dir = config.nestegg.eggs_dir
    co_dir = opath.join(eggs_dir,"_checkout")
    os.makedirs(co_dir,exist_ok=True)
    for pkg in  config.nestegg.source_builds :
        if any(not opath.exists(source_build_file(eggs_dir,pkg, v.dist_file)) 
                    for v in pkg.versions) :
            os.makedirs(source_build_dir(eggs_dir,pkg), exist_ok=True)
            pkg_co_dir=opath.join(co_dir,pkg.name)
            if opath.exists(pkg_co_dir): shutil.rmtree(pkg_co_dir)
            cd(co_dir)
            call([pkg.repo_type, "clone", pkg.repo_url, pkg.name]) 
            cd(pkg_co_dir)
            for version in pkg.versions :
                call([pkg.repo_type, "checkout", version.tag])
                call(["python", "setup.py", "sdist"])
                cp(opath.join(pkg_co_dir,"dist",version.dist_file),
                   source_build_dir(eggs_dir, pkg))
    cd(cwd)

check_source_builds(app.config["config"])

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
    if not opath.exists(opath.join(ne_config.eggs_dir,"index.html")):
        log.debug("Updating base index")
        pkg_idx.scan_all()
        with open(opath.join(ne_config.eggs_dir,"index.html"), "w") as h :
            h.write(gindex.render(pkgs=sorted(pkg_idx.package_pages)))
    return static_file("index.html", root=ne_config.eggs_dir)    

@app.route('/<pkg_name>/')
def get_package(pkg_name):
    pkg_idx.find_packages(Requirement.parse(pkg_name))
    pkg_path = opath.join(ne_config.eggs_dir, pkg_name)
    if not pkg_idx[pkg_name] :
        abort(404, "No such package {}".format(pkg_name))
    pkg_path, html_file = _get_package_html(pkg_path, pkg_name, pkg_idx)
    return static_file(html_file, root=pkg_path)  

@app.route('/<pkg_name>/<egg_name>')
def get_egg(pkg_name, egg_name):
    log.debug("Package: {} egg:{}".format(pkg_name, egg_name))
    pkg_dir = opath.join(ne_config.eggs_dir, pkg_name)
    fpath = opath.join(ne_config.eggs_dir, pkg_name, egg_name)
    if not opath.exists(fpath) :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
        for dist in pkg_idx[pkg_name] :
            if egg_info(dist.location)[0] == egg_name:
                log.debug("Fetch {}/{}".format(pkg_name,egg_name))
                tmp = tempfile.gettempdir()
                try :
                    shutil.move(pkg_idx.download(dist.location, tmp), fpath)
                    return static_file(egg_name, root=pkg_dir)
                except Exception as _e :
                    pass
        abort(404,"No egg found for {} {}".format(pkg_name,egg_name))
    else :
        return static_file(egg_name, root=pkg_dir)

if __name__ == "__main__" :
    run(host='0.0.0.0', port = ne_config.port)
