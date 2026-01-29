import optparse
import sys

import rosdistro


def gen_cache(options, args):
    # touch everything to create the new cache
    distro = rosdistro.RosDistro(args[0], options.cache)
    for r in distro.get_repositories():
        print("Caching %s" % r)
        distro.get_depends1(r)

    print("Cache written to %s" % (distro.depends_file.local_url))


def main():
    parser = optparse.OptionParser()
    parser.add_option("--cache", action="store", default=None)
    (options, args) = parser.parse_args()

    if len(args) != 1:
        print("Usage: %s ros_distro" % sys.argv[0])
        return

    try:
        gen_cache(options, args)
    except Exception as e:
        print(e)
        print("Failure")
    return


if __name__ == "__main__":
    sys.exit(main())
