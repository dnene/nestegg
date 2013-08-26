from bottle import run,route,abort,static_file,SimpleTemplate,default_app,app,request
from hashlib import md5
from pkg_resources import Requirement, resource_string
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
from sh import git, hg, cd, cp
from subprocess import call
from yaml import load, dump
import logging.config
import os
import shutil
import sys
import tempfile
import os.path as opath

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

class Generic: pass
def get_config(data) :
    if isinstance(data, dict) :
        config = Generic()
        for key, value in data.items() :
            setattr(config, key, get_config(value))
        return config
    elif isinstance(data, (list, tuple)) :
        return [get_config(item) for item in data]
    return data
    
def get_app():
    app = default_app()
    default_config = {
        "nestegg_dir" : "{}/.nestegg".format(opath.expanduser('~')),
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
    neconfig = config.nestegg        
    neconfig.pypi_dir = os.path.join(neconfig.nestegg_dir,"pypi")
    neconfig.checkout_dir = os.path.join(neconfig.nestegg_dir,"checkout")
    neconfig.source_dir = os.path.join(neconfig.nestegg_dir,"source_builds")
    neconfig.private_packages = set()
    os.makedirs(neconfig.pypi_dir,0o755, exist_ok=True)
    app.config['config'] = config
    return app

class NesteggPackageIndex(PackageIndex):
    def __init__(self, fresh, *args, **kwargs):
        self.fresh = "fresh" == "1"
        super().__init__(*args,**kwargs)
    
    def process_index(self, url, page):
        if self.fresh: 
            del self.fetched_urls[url]
        super().process_index(url, page)


def source_build_dir(config, pkg_name) : 
    return opath.join(config.nestegg.source_dir, pkg_name)

def source_build_file(config, pkg_name, file_name) : 
    return opath.join(config.nestegg.source_dir, pkg_name, file_name)

def check_source_builds(config):
    cwd = os.getcwd()
    os.makedirs(config.nestegg.checkout_dir,exist_ok=True)
    for pkg in  config.nestegg.source_builds :
        if not hasattr(pkg, "private") : setattr(pkg, "private", False)
        elif pkg.private : config.nestegg.private_packages.add(pkg.name)
        if any(not opath.exists(source_build_file(config,pkg.name, v.dist_file)) 
                    for v in pkg.versions) :
            os.makedirs(source_build_dir(config,pkg.name), exist_ok=True)
            pkg_co_dir=opath.join(config.nestegg.checkout_dir,pkg.name)
            if opath.exists(pkg_co_dir): shutil.rmtree(pkg_co_dir)
            cd(config.nestegg.checkout_dir)
            call([pkg.repo_type, "clone", pkg.repo_url, pkg.name]) 
            cd(pkg_co_dir)
            for ver in pkg.versions :
                call([pkg.repo_type, "checkout", ver.tag])
                call(["python", "setup.py", "sdist"])
                cp(opath.join(pkg_co_dir,"dist",ver.dist_file),
                   source_build_dir(config, pkg.name))
    cd(cwd)

def file_md5(path) :
    m = md5()
    with open(path,"rb") as infile :
        for chunk in iter(lambda: infile.read(8192), b'') :
            m.update(chunk)
    return m.hexdigest()

def get_pkg_html(config, pkg_path, pkg_idx, pkg_name, pindex):
    os.makedirs(pkg_path, exist_ok=True)
    html_file = opath.join(pkg_path, "index.html")
    versions = [] if pkg_name in config.nestegg.private_packages or \
                     not pkg_idx[pkg_name] \
               else [egg_info(d.location) for d in pkg_idx[pkg_name]]
    if pkg_idx.fresh or not opath.exists(html_file) :
        source_pkg_dir = source_build_dir(config, pkg_name)
        if opath.exists(source_pkg_dir) :
            for fname in os.listdir(source_pkg_dir) :
                fpath = opath.join(source_pkg_dir,fname)
                if opath.isfile(fpath) :
                    cp(fpath, pkg_path)
                    versions.append((fname, "md5={}".format(file_md5(fpath))))
        info = {"name" : pkg_name,"versions": versions }
        with open(html_file, "w") as outfile :
            outfile.write(pindex.render(**info))
    return (pkg_path, "index.html")
                
@route('/simple/')
def get_root():
    config, pkg_idx = app.config['config'], app.config['pkg_idx']
    if not opath.exists(opath.join(config.nestegg.pypi_dir,"index.html")):
        log.debug("Updating base index")
        pkg_idx.scan_all()
        with open(opath.join(config.nestegg.pypi_dir,"index.html"), "w") as h :
            h.write(app.config['views'].gindex.render(
                pkgs=sorted(pkg_idx.package_pages)))
    return static_file("index.html", root=config.nestegg.pypi_dir)    

def is_valid_package(config, pkg_idx, pkg_name) :
    if pkg_name in config.nestegg.private_packages : return True
    if  opath.exists(source_build_dir(config, pkg_name)) :
        if not pkg_idx[pkg_name] :
            config.nestegg.private_packages.add(pkg_name)
        return True
    return True if pkg_idx[pkg_name] else False

@route('/simple/<pkg_name>/')
def get_package(pkg_name):
    config, pkg_idx = request.app.config['config'], request.app.config['pkg_idx']
    if pkg_name not in config.nestegg.private_packages :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
    pkg_path = opath.join(config.nestegg.pypi_dir, pkg_name)
    if is_valid_package(config, pkg_idx, pkg_name) :
        root, html = get_pkg_html(config, pkg_path, pkg_idx, pkg_name,
                request.app.config['views'].pindex)
        return static_file(html, root=root)  
    else:
        abort(404, "No such package {}".format(pkg_name))

@route('/simple/<pkg_name>/<egg_name>')
@route('/simple/<pkg_name>/<egg_name>/')
def get_egg(pkg_name, egg_name):
    config, pkg_idx = request.app.config['config'], request.app.config['pkg_idx']
    log.debug("Package: {} egg:{}".format(pkg_name, egg_name))
    pkg_dir = opath.join(config.nestegg.pypi_dir, pkg_name)
    if not egg_name.startswith(pkg_name) :
        egg_name="{}-{}.".format(pkg_name,egg_name)
        if opath.exists(pkg_dir) :
            for fname in os.listdir(pkg_dir) :
                if fname.startswith(egg_name) and fname != egg_name :
                    egg_name = fname
                    break
    fpath = opath.join(config.nestegg.pypi_dir, pkg_name, egg_name)
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

def main() :
    app = get_app()  
    config = app.config['config']
    pkg_idx = NesteggPackageIndex(config.nestegg.fresh, config.nestegg.index_url)
    app.config['pkg_idx'] = pkg_idx
    check_source_builds(app.config["config"])
    app.config['views'] = Generic()
    app.config['views'].pindex = \
        SimpleTemplate(resource_string('nestegg','views/package.tpl'))
    app.config['views'].gindex = \
        SimpleTemplate(resource_string('nestegg','views/all_packages.tpl'))
    run(app=app, host='0.0.0.0', port = config.nestegg.port)

if __name__ == "__main__" :
    main()
