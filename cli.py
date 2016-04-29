import sys
from artemis.tool import Artemis


def usage(tool):
    print "Usage: %s <command> [arguments]\n\nPossible commands:" % sys.argv[0]
    for name, args, doc in tool.get_callable_methods():
        print name
        print "\t\t%s" % (doc if doc else "(Undocumented)")
        print "\t\tArguments:"
        for a in args:
            print "\t\t--%s=<value>" % a


def run_cli(tool):
    if len(sys.argv) < 2 or sys.argv[1] == 'help':
        usage(tool)
        return
    try:
        method = getattr(tool, "call_" + sys.argv[1].replace("-", "_"))
    except:
        print "Command not found: %s\n" % sys.argv[1]
        usage(tool)
        return

    args = {}
    prevarg = ""
    for a in sys.argv[2:]:
        if a[:2] != '--':
            if prevarg == "":
                print "Invalid argument: %s\n" % a
                print usage(tool)
                return
            args[prevarg] = a
        else:
            if '=' in a:
                arg_name, arg_value = a[2:].split('=')
            else:
                arg_name = a[2:]
                arg_value = True
            args[arg_name.replace("-", "_")] = arg_value
            prevarg = arg_name.replace("-", "_")

    print method(**args)


tool = Artemis(config_file='config.yml')
run_cli(tool)
