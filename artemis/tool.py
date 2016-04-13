import sys
import os
import yaml
import subprocess


class Artemis(object):
    def __init__(self, config_file='config.yml'):
        with open(config_file, 'r') as f:
            self.config = yaml.load(f)
        self.environments = self.__get_environment_list()

    def get_environments(self):
        return self.environments

    def get_environment(self, name):
        for e in self.get_environments():
            if e.get_name() == name:
                return e

    def create_environment(self, name, version):
        if os.path.isdir("environments/" + name):
            print "Environment %s exists already" % name
            return

        self._update_env_specs()
        if not os.path.isdir("skeletons/" + version):
            print "Version %s does not exist" % version
            return
        print "Creating environment %s, version %s" % (name, version)
        env = Environment(name, version)
        self.environments.append(env)

    def provision_environment(self, env):
        print self._kubectl("create namespace %s" % env.get_name())
        for cmd in self.config['kubeinit']:
            print self._kubectl("--namespace %s %s" % (env.get_name(),cmd))

        for c in env.get_components():
            if c.get_type() == 'kube':
                print "Provisioning kubernetes component %s" % c.get_name()
                print self._kubectl("create -f -", input=open(c.get_file(), 'r'))

    def teardown_environment(self, env):
        print self._kubectl("delete namespace %s" % env.get_name())

    def update_component(self, env_name, comp_name, image_tag):
        env = self.get_environment(env_name)
        comp = env.get_component(comp_name)
        comp.set_image_tag(image_tag)
        self._kubectl("--namespace=%s rolling-update %s --image=%s" % (env.get_name(),
                                                                      comp.get_name(),
                                                                      comp.get_image_name()))

    def get_component_uptime(self, env_name, component_name):
        return self._kubectl("--namespace=%s get po --selector=app=%s|tail -n1|awk '{ print $5}'" % (env_name, component_name))

    def get_component_pod_name(self, env_name, component_name):
        return self._kubectl("--namespace=%s get po --selector=app=%s|tail -n1|awk '{ print $1}'" % (env_name, component_name))

    def __get_environment_list(self):
        return [Environment(i, self.__read_env_version(i))
                for i in os.listdir("environments/")]

    def __get_kube_environment_list(self):
        return [{'name': env.split(" ")[0], 'version': env.split(" ")[1]}
                for env in self._kubectl("get namespaces -L env_version"
                                          "awk '{ print $1,$4 }' | "
                                          "tail -n+2 | "
                                          "grep -v default | "
                                          "grep -v kube-system"
                                          ).split("\n") if ' ' in env]

    def __read_env_version(self, env_name):
        with open("environments/" + env_name + "/VERSION", 'r') as f:
            return f.readline()

    def _kubectl(self, cmd, input=None):
        return subprocess.check_output(
            "%s %s" %
            (self.config.get('kubectl'), cmd), shell=True, stdin=input)

    def _update_env_specs(self):
        if os.path.isdir("skeletons/"):
            print subprocess.check_output("cd skeletons && git pull", shell=True)
        else:
            print subprocess.check_output("git clone %s skeletons" % self.config.get('spec_repo'), shell=True)

    def run_cli(self):
        if len(sys.argv) < 2:
            return

        if sys.argv[1] == 'list-envs':
            envs = self.get_environments()
            if not len(envs):
                print "No environments."
                return
            
            print "Created environments:"
            for e in envs:
                print e

        if sys.argv[1] == 'list-components':
            env = self.get_environment(sys.argv[2])
            if not env:
                print "No such environment"
                return
            print "Components in %s:" % env.get_name()
            for c in env.get_components():
                print c

        if sys.argv[1] == 'create':
            self.create_environment(sys.argv[2], sys.argv[3])

        if sys.argv[1] == 'build':
            env = self.get_environment(sys.argv[2])
            print "Building %s" % env.get_name()
            self.provision_environment(env)

        if sys.argv[1] == 'teardown':
            env = self.get_environment(sys.argv[2])
            print "Tearing down %s" % env.get_name()
            self.teardown_environment(env)

        if sys.argv[1] == 'get-image-tag':
            env = self.get_environment(sys.argv[2])
            comp = env.get_component(sys.argv[3])
            print "Tag for %s in %s: %s" % (comp.get_name(),
                                            env.get_name(),
                                            comp.get_image_tag())
        if sys.argv[1] == 'get-image-name':
            env = self.get_environment(sys.argv[2])
            comp = env.get_component(sys.argv[3])
            print "Name for %s in %s: %s" % (comp.get_name(),
                                            env.get_name(),
                                            comp.get_image_name())

        if sys.argv[1] == 'set-image-tag':
            env = self.get_environment(sys.argv[2])
            comp = env.get_component(sys.argv[3])
            print "Old tag: %s" % comp.get_image_tag()
            comp.set_image_tag(sys.argv[4])
            print "New tag: %s" % comp.get_image_tag()
            self._kubectl("--namespace=%s rolling-update %s --image=%s" % (env.get_name(),
                                                                          comp.get_name(),
                                                                          comp.get_image_name()))


class Environment(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version
        self.components = []

        if not os.path.isdir(self.__get_env_dir()):
            self.__make_spec()
        else:
            self.__read_spec()

    def get_name(self):
        return self.name

    def get_version(self):
        return self.version

    def get_component(self, name):
        for c in self.components:
            if c.get_name() == name:
                return c

    def get_components(self, resource_type=''):
        if not resource_type:
            return self.components
        else:
            return [c for c in self.components if c.get_type() == resource_type]

    def __make_spec(self):
        print "Copying environment spec from %s" % self.__get_skel_dir()
        os.mkdir(self.__get_env_dir())

        for i in os.listdir(self.__get_skel_dir()):
            file_path = os.path.join(self.__get_skel_dir(), i)
            if not os.path.isfile(file_path):
                continue
            env_file_path = os.path.join(self.__get_env_dir(), i)
            with open(file_path, 'r') as s, open(env_file_path, 'w') as t:
                for line in s:
                    t.write(line.replace("ENV_NAME", self.name))

            with open(os.path.join(self.__get_env_dir(), "VERSION"), 'w') as f:
                f.write(self.version + "\n")

            comp = self.__gen_component(env_file_path)
            self.components.append(comp)

    def __read_spec(self):
        for i in os.listdir(self.__get_env_dir()):
            file_path = os.path.join(self.__get_env_dir(), i)
            if not os.path.isfile(file_path) or i == 'VERSION':
                continue
            self.components.append(self.__gen_component(file_path))

    def __gen_component(self, file_path):
        file_name, file_extension = os.path.splitext(file_path)
        return Component(
            name=file_name.split("/")[-1] if '/' in file_name else file_name,
            file=file_path,
            component_type='kube' if file_extension == '.yaml' else 'tf',
            env=self)

    def __get_skel_dir(self):
        return "skeletons/%s" % self.version

    def __get_env_dir(self):
        return "environments/%s" % self.name

    def __str__(self):
        return self.name


class Component(object):
    def __init__(self, name, file, component_type, env):
        self.name = name
        self.file = file
        self.type = component_type
        self.env = env

    def get_name(self):
        return self.name

    def get_type(self):
        return self.type

    def get_file(self):
        return self.file

    def get_spec(self):
        return self.__read_spec() if self.type == 'kube' else ''

    def set_spec(self, spec):
        if self.type != 'kube':
            return
        self.__write_spec(spec)

    def get_image_tag(self):
        try:
            return self.get_image_name().split(":")[1]
        except:
            return ""

    def get_image_basename(self):
        try:
            return self.get_image_name().split(":")[0]
        except:
            return ""

    def get_image_name(self):
        if self.type != 'kube':
            return
        spec = self.__read_spec()
        if spec['kind'] != 'ReplicationController':
            return ""

        try:
            return spec['spec']['template']['spec']['containers'][0]['image']
        except:
            return ""

    def set_image_tag(self, new_tag):
        if self.type != 'kube':
            return
        if new_tag == '':
            raise ValueError
        spec = self.__read_spec()
        if spec['kind'] != 'ReplicationController':
            return
        image_name, image_tag = spec['spec']['template']['spec']['containers'][0]['image'].split(":")
        spec['spec']['template']['spec']['containers'][0]['image'] = image_name + ":" + new_tag
        self.__write_spec(spec)

    def __read_spec(self):
        with open(self.file, 'r') as f:
            return yaml.load(f)

    def __write_spec(self, spec):
        with open(self.file, 'w') as f:
            f.write(yaml.dump(spec))

    def __str__(self):
        return self.name + " [" + self.type + "]: " + self.file