import optparse
import sys

import rosdistro


def depends(args):
    distro = rosdistro.RosDistro(args[1])
    deps = distro.get_depends(args[2:], int(args[0]))
    for t, dep in deps.iteritems():
        print('%s depends:' % t)
        print(', '.join(dep))


def depends_on(args):
    distro = rosdistro.RosDistro(args[1])
    deps = distro.get_depends_on(args[2:], int(args[0]))
    for t, dep in deps.iteritems():
        print('%s depends_on:' % t)
        print(', '.join(dep))


def help(cmd=None):
    print("Usage: %s [command]" % sys.argv[0])
    print("   With [command] one of the following")
    if cmd and type(cmd) == list:
        cmd = cmd[0]
    if cmd and cmd not in cmds:
        print("Unknown command %s" % cmd)
        cmd = None
    if cmd and cmd == 'help':
        cmd = None
    for c, ops in cmds.iteritems():
        res = "     '%s'" % c
        res += (' ' * (30 - len(res)))
        res += "with arguments: '%s'" % (' '.join(ops['args']))
        if not cmd or cmd == c:
            print(res)


cmds = {'help': {'args': ['command'], 'cmd': help},
        'depends': {'args': ['depth', 'ros_version', 'package_list'], 'cmd': depends},
        'depends_on': {'args': ['depth', 'ros_version', 'package_list'], 'cmd': depends_on}}


def main():
    parser = optparse.OptionParser()
    parser.add_option("--cache", action="store", default=None)
    (options, commands) = parser.parse_args()

    # usage
    if len(commands) == 0:
        help()
        return

    # command specific usage
    cmd = commands[0]
    if cmd in cmds:
        args = cmds[cmd]['args']
        if len(commands) - 1 < len(args):
            help(cmd)
            return
    else:
        help(cmd)
        return

    # execute command
    try:
        cmds[cmd]['cmd'](commands[1:])
    except Exception as e:
        print(e)
        print("Failure")
    return

    distro = rosdistro.RosDistro(args(0), options.cache)
    for r in distro.get_repositories():
        print("Caching %s" % r)
        distro.get_depends1(r)

    print("Cache written to %s" % (distro.depends_file.local_url))


if __name__ == "__main__":
    sys.exit(main())
