nestegg
=======

.. contents::

Continuous Integration server and on-demand, lightweight, package building pypi mirror

Features 
--------

.. note :: 

  Still in early stages and not yet entirely stable, actively being worked on.

**Implemented**

* **Continuous integration**: Test all defined source builds at defined intervals (implemented). 

  * Pending: 
    
    * Run tests based on git / hg commits. 
    * Offer readonly web based interface to past tests and results

* **Pypi like repository**: For software you author or python libraries you modify but only publish internally
* **Pypi Mirror**: Mirrors packages from pypi.python.org. 

  * *On demand*: Packages are downloaded only when requested for. 
  * *Lightweight*: Downloads and mirrors only those versions requested for.

**TODO**

* Apache integration using mod_wsgi
* Refresh pypi packages and indices
* Additional python versions (currently tested only with python 3.3)

Quick start
-----------

* Create and activate a python virtual environment

  * Currently only tested with python version 3.3. Support for additional versions to be added later. 

* Install package::

    $ pip install http://github.com/dnene/nestegg/tarball/master

* Create configuration file for nestegg in your home directory `$HOME/nestegg.yml` ::

.. code:: yml

  storage_dir: /var/cache/nestegg                         # Where nestegg makes a nest
  port: 7654                                              # Port to run on
  index-url: https://pypi.python.org/simple               # Pypi Index URL
  refresh_interval: 1d                                    # Frequency to check for new versions
  repositories :                                          # List of source builds
    - name: my_package_name                               # package name
      vcs: git                                            # git and hg supported
      url: git@mygithost.com:myuserid/mypackage.git       # git url here
                                                          # could also be file:///.....
      private: Yes                                        # private or public
                                                          # Private if package does not exist on pypi
      releases:                                           # Packages built for these
        - version: 1.0.0                                  # python version
          tag: 1.0.0                                      # [not required if same as version]
                                                          # the git/hg branch/tag name
          dist_file: mypackage-1.0.0.tar.gz               # not required if same as 
                                                          #    {tag}-{version}-{.tar.gz|.zip|.egg}
                                                          # source dist file name
          python: /usr/bin/python2.7                      # optional. Required only if you want 
                                                          # particular version of python to run "sdist"
    - name: package_to_be_tested
      vcs: git
      url: file:////project_dir                           # could be remote repo also (as above)
      private: Yes
      branches:                                           # List your testable software here
        - name: master
          dist_file: package-version.tar.gz
          python: /usr/bin/mypython                       # python exe to use for running tests
          schedule:                                       # schedule for triggering tests
            hour: *                                       # cron like parameters for APScheduler
            minute: *

For each release / version defined, nestegg will :

* Create a git or hg clone from the git / hg repo
* Checkout the defined tag / branch
* Create a source distribution using `python setup.py sdist`
* Publish the distribution to the nestegg package repository. 
* You can install/use the distribution using pip, easy_install etc.

For each release / branch defined nestegg will :
* Clone the branch from git or hg
* Run tests on the branch at predefined intervals

All the source builds and versions you defined will be cloned, the corresponding tag checked out and source distributi

* Start nestegg server::

.. code:: 

  $ nestegg
  Bottle v0.11.6 server starting up (using WSGIRefServer())...
  Listening on http://0.0.0.0:7654/
  Hit Ctrl-C to quit.

Use http://localhost:7654/simple as the index url with pip or tox or other clients. eg. ::

  $ pip install SQLAlchemy==0.8.2 --index-url=http://localhost:7654/simple 


Goals
-----

* Continuous Integration tool for python packages
* Run tests based on :

  * Predefined cron like schedules
  * Signals from git / hg clients
  * Explicit commands

* Create a desktop / intranet mirror of all packages used. Create new test virtualenvs readily without having to wait for long downloads
* Manage versions of your package dependencies (even if pypi eventually unpublishes the versions you rely upon)
* Publish versions of libraries you fork, or any you create to a pypi like repository without having to publish it globally.
* Access control on git / hg repos can make it hard to use github / bitbucket tarballs in dependency_links. This circumvents that issue.
