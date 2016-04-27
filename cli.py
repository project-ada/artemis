import sys
from artemis.tool import Artemis


def run_cli(tool):
    if len(sys.argv) < 2:
        return

    if sys.argv[1] == 'list-envs':
        envs = tool.get_environments()
        if not len(envs):
            print "No environments."
            return

        print "Created environments:"
        for e in envs:
            print e

    if sys.argv[1] == 'list-components':
        env = tool.get_environment(sys.argv[2])
        if not env:
            print "No such environment"
            return
        print "Components in %s:" % env.get_name()
        for c in env.get_components():
            print c

    if sys.argv[1] == 'create':
        tool.create_environment(sys.argv[2], sys.argv[3])

    if sys.argv[1] == 'tf':
        tool._terraform(' '.join(sys.argv[2:]))

    if sys.argv[1] == 'build':
        env = tool.get_environment(sys.argv[2])
        print "Building %s" % env.get_name()
        tool.provision_environment(env)

    if sys.argv[1] == 'refresh-spec':
        env = tool.get_environment(sys.argv[2])
        print "Calling refresh on %s" % env.get_name()
        tool.refresh_environment(env)

    if sys.argv[1] == 'teardown':
        env = tool.get_environment(sys.argv[2])
        print "Tearing down %s" % env.get_name()
        tool.teardown_environment(env)

    if sys.argv[1] == 'get-image-tag':
        env = tool.get_environment(sys.argv[2])
        comp = env.get_component(sys.argv[3])
        print "Tag for %s in %s: %s" % (comp.get_name(),
                                        env.get_name(),
                                        comp.get_image_tag())

    if sys.argv[1] == 'recreate':
        env = tool.get_environment(sys.argv[2])
        component = env.get_component(sys.argv[3])
        tool.recreate_component(component)

    if sys.argv[1] == 'create-endpoints':
        env = tool.get_environment(sys.argv[2])
        tool.create_endpoints(env)

    if sys.argv[1] == 'list-endpoints':
        env = tool.get_environment(sys.argv[2])
        tool.list_endpoints(env)

    if sys.argv[1] == 'remove-endpoints':
        env = tool.get_environment(sys.argv[2])
        tool.remove_endpoints(env)

    if sys.argv[1] == 'get-image-name':
        env = tool.get_environment(sys.argv[2])
        comp = env.get_component(sys.argv[3])
        print "Name for %s in %s: %s" % (comp.get_name(),
                                         env.get_name(),
                                         comp.get_image_name())

    if sys.argv[1] == 'set-image-tag':
        env = tool.get_environment(sys.argv[2])
        comp = env.get_component(sys.argv[3])
        print "Old tag: %s" % comp.get_image_tag()
        comp.set_image_tag(sys.argv[4])
        print "New tag: %s" % comp.get_image_tag()
        tool._kubectl("--namespace=%s rolling-update %s --image=%s" % (env.get_name(),
                                                                       comp.get_name(),
                                                                       comp.get_image_name()))


tool = Artemis(config_file='config.yml')
run_cli(tool)
