import sys
import os
import ConfigParser
from os.path import exists as pathexists
from os.path import splitext
from subprocess import Popen

def make_venv(repo, stateconf):
    """Make a virtualenv for the specified repo"""
    # TODO read a user or site wide config file for whether to use virtualenvwrapper
    # could have a "make virtualenv config with a possible 'internal' value"
    p = Popen(["mkvirtualenv", "%s/.venv" % repo])
    p.wait()

def venv(repo):
    """Check the repo has a venv"""

    # Why do we need a state file again?
    stateconf = "%s/.vehstate.conf" % repo
    if not pathexists(stateconf):
        make_venv(repo, stateconf)

    config = ConfigParser.ConfigParser()
    with open(stateconf) as fd:
        config.readfp(fd)
    vepath = config.get("ve", "path")
    print vepath




def edit_file(filename):
    """Open the filename in the editor.

    Actually does the whole pattern of opening a temp file.
    """
    _, extension = splitext(filename)
    from tempfile import mkstemp
    try:
        fd, tempfilename = mkstemp(suffix=".conf", text=True)
        print os.write(fd, CFG_TEMPLATE + "\n")
        os.close(fd)
    except Exception, e:
        print >>sys.stderr, "problem making temp file: " + str(e)
    else:
        editor = os.environ.get("VISUAL", os.environ.get("EDITOR", "edit"))
        try:
            p = Popen([editor, tempfilename])
            p.wait()
        except Exception, e:
            print >>sys.stderr, "problem running editor"
        else:
            # Copy the temp file in
            if pathexists(filename):
                os.remove(filename)
            os.rename(tempfilename, filename)

class Exists(Exception):
    """File exists"""
    pass

CFG_TEMPLATE="""[packages]
# enter package names here like
#   package = packagename
# the package names are passed directly to pip.
# This makes it easy to use either a pypi name:
#   package = packagename
# or a url:
#   package = http://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.4.9.tar.gz#md5=c49067cab242b5ff8c7b681a5a99533a
# or a vc reference:
#   package = hg+http://domain/repo


# End
"""
def install(repo):
    """Install a veh config file

    Opens VISUAL (and EDITOR if it can't find that) with a template.
    """
    # TODO I think this should commit really. For now, it doesn't.
    # TODO we need to add the line to hgignore for the state file
    cfgfile = "%s/.veh.conf" % repo
    if pathexists(cfgfile):
        raise Exists(cfgfile)
    edit_file(cfgfile)

def edit(repo):
    """Edit the veh config file

    Opens VISUAL on the veh config file."""
    cfgfile = "%s/.veh.conf" % repo
    if pathexists(cfgfile):
        edit_file(cfgfile)

def main():
    from optparse import OptionParser
    p = OptionParser()
    o,a = p.parse_args(sys.argv[1:])

    # We ought to check the repo argument here
    repo = a.pop(0)

    # Now run the command
    command = a.pop(0)
    if command == "cd":
        os.chdir(repo)
        os.execl(os.environ["SHELL"])
    elif command == "noop":
        venv(repo)
    elif command == "install":
        install(repo)
    elif command == "edit":
        edit(repo)
    else:
        print "unknown command"


if __name__== "__main__":
    main()

# End

    
