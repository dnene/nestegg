from bottle import run,route,abort,static_file,SimpleTemplate,default_app,app,request,redirect
from hashlib import md5
from pkg_resources import Requirement, resource_string
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
from sh import git, hg, cd, cp
from subprocess import call
from yaml import load, dump
from requests import head
import logging.config
import os
import shutil
import sys
import tempfile
import os.path as opath

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class NesteggException(Exception): pass
class Generic(object): pass

def lookup_config_file(filename):
    for f in [opath.join(opath.expanduser('~'), filename),
              '/etc/{}'.format(filename) ] :
        if opath.exists(f) : return f
    raise NesteggException("Cannot find config file {}".format(filename))

def get_config(data) :
    if isinstance(data, dict) :
        config = Generic()
        for key, value in data.items() :
            setattr(config, key, get_config(value))
        return config
    elif isinstance(data, (list, tuple)) :
        return [get_config(item) for item in data]
    return data

def scan_packages(config) :
    packages = {}
    for dirname in os.listdir(config.pypi_dir) :
        if opath.isdir(opath.join(config.pypi_dir,dirname)) :
            packages[dirname.lower()] = dirname
    config.runtime.packages = packages

def get_app():
    app = default_app()
    default_config = {
        "nestegg_dir" : "{}/.nestegg".format(opath.expanduser('~')),
        "index_url": "https://pypi.python.org/simple",
        "port": 7654,  "fresh": "0",
    }
    config_file = lookup_config_file("nestegg.yml")
    if config_file :
        with open(config_file,"r") as in_config :
            config = get_config(load(in_config))
        for key, value in default_config.items() :
            if not hasattr(config,key): 
                setattr(config,key,value)
    else :
        config = get_config(default_config)

    config.pypi_dir = os.path.join(config.nestegg_dir,"pypi")
    config.checkout_dir = os.path.join(config.nestegg_dir,"checkout")
    config.source_dir = os.path.join(config.nestegg_dir,"source_builds")
    config.archives_dir =os.path.join(config.nestegg_dir,"archived_builds")
    config.private_packages = set()
    config.runtime = Generic()
    os.makedirs(config.pypi_dir,0o755, exist_ok=True)
    scan_packages(config)
    app.config['ctx'] = config
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
    return opath.join(config.source_dir, pkg_name)

def archives_dir(config, pkg_name) : 
    return opath.join(config.archives_dir, pkg_name)

def source_build_file(config, pkg_name, file_name) : 
    return opath.join(config.source_dir, pkg_name, file_name)

def check_source_builds(config):
    cwd = os.getcwd()
    os.makedirs(config.checkout_dir,exist_ok=True)
    for pkg in  config.source_builds :
        if not hasattr(pkg, "private") : setattr(pkg, "private", False)
        elif pkg.private : config.private_packages.add(pkg.name)
        if any(not opath.exists(source_build_file(config,pkg.name, v.dist_file)) 
                    for v in pkg.versions) :
            os.makedirs(source_build_dir(config,pkg.name), exist_ok=True)
            pkg_co_dir=opath.join(config.checkout_dir,pkg.name)
            if opath.exists(pkg_co_dir): shutil.rmtree(pkg_co_dir)
            cd(config.checkout_dir)
            call([pkg.repo_type, "clone", pkg.repo_url, pkg.name]) 
            cd(pkg_co_dir)
            for ver in pkg.versions :
                pyexe = "python" if not hasattr(ver,"python") else ver.python
                print("Python is {}".format(pyexe))
                call([pkg.repo_type, "checkout", ver.tag])
                call([pyexe, "setup.py", "sdist"])
                cp(opath.join(pkg_co_dir,"dist",ver.dist_file),
                   opath.join(source_build_dir(config, pkg.name),
                       ver.dist_file))
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
    if pkg_name in config.private_packages or not pkg_idx[pkg_name] :
      versions = {}
    else :
        versions = dict((egg_info(d.location) for d in pkg_idx[pkg_name]))
    if pkg_idx.fresh or not opath.exists(html_file) :
        archives_pkg_dir = archives_dir(config, pkg_name)
        if opath.exists(archives_pkg_dir) :
            for fname in os.listdir(archives_pkg_dir) :
                fpath = opath.join(archives_pkg_dir,fname)
                if opath.isfile(fpath) :
                    cp(fpath, pkg_path)
                    versions[fname] =  "md5={}".format(file_md5(fpath))
        source_pkg_dir = source_build_dir(config, pkg_name)
        if opath.exists(source_pkg_dir) :
            for fname in os.listdir(source_pkg_dir) :
                fpath = opath.join(source_pkg_dir,fname)
                if opath.isfile(fpath) :
                    cp(fpath, pkg_path)
                    versions[fname] =  "md5={}".format(file_md5(fpath))
        info = {"name" : pkg_name,"versions": versions }
        with open(html_file, "w") as outfile :
            outfile.write(pindex.render(**info))
    return (pkg_path, "index.html")
                
@route('/simple/')
def get_root():
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    if not opath.exists(opath.join(config.pypi_dir,"index.html")):
        log.debug("Updating base index")
        pkg_idx.scan_all()
        with open(opath.join(config.pypi_dir,"index.html"), "w") as h :
            h.write(app.config['views'].gindex.render(
                pkgs=sorted(pkg_idx.package_pages)))
    return static_file("index.html", root=config.pypi_dir)    

def is_valid_package(config, pkg_idx, pkg_name) :
    if pkg_name in config.private_packages : return True
    if opath.exists(archives_dir(config, pkg_name)) : return True
    if opath.exists(source_build_dir(config, pkg_name)) :
        if not pkg_idx[pkg_name] :
            config.private_packages.add(pkg_name)
        return True
    return True if pkg_idx[pkg_name] else False

def get_real_mixed_case_name(config, pkg_name):
    mixed_case_name = config.runtime.packages.get(pkg_name.lower(),None)
    if mixed_case_name and mixed_case_name == pkg_name :
        return pkg_name
    response = head("https://pypi.python.org/simple/{}/".format(pkg_name))
    if 200 <= response.status_code < 300 : return pkg_name
    elif response.status_code < 400 :
        new_pkg_name = response.headers["location"].split("/")[-1]
        if pkg_name.lower() == new_pkg_name.lower() :
            config.runtime.packages[pkg_name.lower()] = new_pkg_name 
            return new_pkg_name
    raise NesteggException(
        "Unable to get mixed case package name for {}".format(pkg_name))
    
@route('/simple/<pkg_name>/')
def get_package(pkg_name):
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    real_pkg_name = get_real_mixed_case_name(config,pkg_name)
    if real_pkg_name != pkg_name :
        redirect('/simple/{}/'.format(real_pkg_name))
    if pkg_name not in config.private_packages :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
    pkg_path = opath.join(config.pypi_dir, pkg_name)
    if is_valid_package(config, pkg_idx, pkg_name) :
        root, html = get_pkg_html(config, pkg_path, pkg_idx, pkg_name,
                request.app.config['views'].pindex)
        return static_file(html, root=root)  
    else:
        abort(404, "No such package {}".format(pkg_name))

@route('/simple/<pkg_name>/<egg_name>')
@route('/simple/<pkg_name>/<egg_name>/')
def get_egg(pkg_name, egg_name):
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    log.debug("Package: {} egg:{}".format(pkg_name, egg_name))
    pkg_dir = opath.join(config.pypi_dir, pkg_name)
    if not egg_name.startswith(pkg_name) :
        egg_name="{}-{}.".format(pkg_name,egg_name)
        if opath.exists(pkg_dir) :
            for fname in os.listdir(pkg_dir) :
                if fname.startswith(egg_name) and fname != egg_name :
                    egg_name = fname
                    break
    fpath = opath.join(config.pypi_dir, pkg_name, egg_name)
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
    config = app.config['ctx']
    pkg_idx = NesteggPackageIndex(config.fresh, config.index_url)
    app.config['pkg_idx'] = pkg_idx
    check_source_builds(app.config["ctx"])
    app.config['views'] = Generic()
    app.config['views'].pindex = \
        SimpleTemplate(resource_string('nestegg','views/package.tpl'))
    app.config['views'].gindex = \
        SimpleTemplate(resource_string('nestegg','views/all_packages.tpl'))
    run(app=app, host='0.0.0.0', port = config.port)

if __name__ == "__main__" :
    main()
