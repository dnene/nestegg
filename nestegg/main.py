import os, shutil, sys, tempfile, os.path as opath, configparser
from bottle import run, abort, static_file, SimpleTemplate, default_app
from pkg_resources import Requirement
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
from subprocess import call
import sh
from sh import git, hg, cd, cp
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

#            if build_tuple[0] == "hg" :
                
            
    
def get_app():
    app = default_app()
    config = configparser.ConfigParser()
    app.config["config"] = config
    config['nestegg'] = {
        "eggs_dir" : "{}/.nestegg/cache".format(opath.expanduser('~')),
        "index_url": "https://pypi.python.org/simple",
        "port": 7654,  "fresh": "0",
    }
    config_file = get_default_config_file()
    if config_file :
        with open(config_file,"r") as in_config :
            config.read_file(in_config)
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
eggs_dir, index_url, fresh = [app.config["config"]["nestegg"][attr] 
        for attr in ("eggs_dir", "index_url", "fresh")] 
os.makedirs(eggs_dir,0o755, exist_ok=True)
pkg_idx = NesteggPackageIndex(fresh, index_url)

class NesteggException(Exception):
    def __init__(self, value, cause=None) :
        self.value = value
        self.cause = cause
    def __str__(self) :
        return repr(self.value)

def errorable(error_str) :
    def wrapper(f) :
        def inner(**kwargs) :
            cause = None
            try :
                ret = f(**kwargs) 
            except Exception as e:
                cause = e
            if cause or (ret and ret != 0) :
                print(kwargs)
                raise NesteggException(error_str.format_map(kwargs), cause)
        return inner
    return wrapper

@errorable("Cannot create directory {co_dir}")
def to_checkout_dir(co_dir) :
    if opath.exists(co_dir): shutil.rmtree(co_dir)
    os.makedirs(co_dir,exist_ok=True)
    cd(co_dir)

@errorable("Cannot checkout repo {repo_type}:{repo}:{tag}")
def checkout(rtyp, repo, tag, dir_name) :
    gmap = { "hg" : ("hg", "-u"), "git": ("git", "-b") }
    return call([gmap[rtyp][0], "clone", gmap[rtyp][1], tag, repo, dir_name]) 

@errorable("Cannot create sdist for {package_name}:{tag_name}")
def do_sdist(package_name, tag_name) :
    cd(tag_name)
    return call(["python", "setup.py", "sdist"])

@errorable("Cannot copy sdist for {pkg_name}:{tag}:{dist_file}")
def copy_sdist(eggs_dir, pkg_name, tag, dist_file):
    os.makedirs(opath.join(eggs_dir, "_custom", pkg_name), exist_ok=True)
    cp(opath.join(eggs_dir, "_checkout", pkg_name, tag, "dist", dist_file),
       opath.join(eggs_dir, "_custom_builds", pkg_name, dist_file))


def check_custom_builds(config):
    for pkg_name, builds in list((sec.split("_")[-1], 
        list((ver, config[sec][ver].split("|")) for ver in config[sec])) 
            for sec in config if sec.startswith("nestegg_builds")) :
        for tag, (rtyp, repo, dfile) in builds :
            ensure_dist(pkg_name, rtyp, repo, tag, dfile)

def ensure_dist(pkg_name, rtyp, repo, tag, dfile) :
    dist_file = opath.join(eggs_dir, "_custom_builds", pkg_name, dfile) 
    if not opath.exists(dist_file) :
        to_checkout_dir(co_dir=opath.join(eggs_dir,"_checkout",pkg_name))
        checkout(rtyp=rtyp, repo=repo, tag=tag, dir_name=tag)
        do_sdist(package_name=pkg_name, tag_name=tag)
        os.makedirs(opath.dirname(dist_file), exist_ok=True)
        cp(opath.join(eggs_dir, "_checkout", pkg_name, tag, "dist", dfile), 
                dist_file)

check_custom_builds(app.config["config"])

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
                try :
                    shutil.move(pkg_idx.download(dist.location, tmp), fpath)
                    return static_file(egg_name, root=pkg_dir)
                except Exception as _e :
                    pass
        abort(404,"No egg found for {} {}".format(pkg_name,egg_name))
    else :
        return static_file(egg_name, root=pkg_dir)

if __name__ == "__main__" :
    run(host='0.0.0.0', port = app.config["config"]["nestegg"]["port"])
