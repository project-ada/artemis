import sys
import os
import yaml
import subprocess
import shutil
import route53
import inspect
import socket


class Artemis(object):
    def __init__(self, config_file='config.yml'):
        with open(config_file, 'r') as f:
            self.config = yaml.load(f)
        self._update_env_list()
        if self.config.get('endpoint_zone', False):
            conn = route53.connect(
                aws_access_key_id=self.config.get('aws_access_key'),
                aws_secret_access_key=self.config.get('aws_secret_key')
                )
            for z in conn.list_hosted_zones():
                if z.name == self.config.get('endpoint_zone'):
                    self.endpoint_zone = conn.get_hosted_zone_by_id(z.id)
        else:
            self.endpoint_zone = False

    def valid_ip(self, address):
        try:
            socket.inet_aton(address)
            return True
        except:
            return False

    def get_environments(self):
        return self.environments

    def get_environment(self, name):
        for e in self.get_environments():
            if e.get_name() == name:
                return e

    def get_callable_methods(self):
        for name, data in inspect.getmembers(self):
            if name[:5] == 'call_':
                yield (name[5:].replace("_", "-"),
                       [a.replace("_", "-") for a in inspect.getargspec(data).args if a is not 'self'],
                       data.__doc__)

    def call_list_environments(self):
        """Return a list of environments."""

        return self.environments

    def call_list_components(self, env_name):
        """Return a list of components in an environment."""

        env = self.get_environment(env_name)
        return env.get_components()

    def call_create_environment(self, env_name, version):
        """Create an environment with the specified name and version."""
        if os.path.isdir("environments/" + env_name):
            print "Environment %s exists already" % env_name
            return

        if self.config.get('spec_use_git', False):
            self._update_env_specs()

        if not os.path.isdir("%s/%s" % (self.config.get('spec_dir'), version)):
            print "Version %s does not exist" % version
            return
        print "Creating environment %s, version %s" % (env_name, version)
        env = Environment(env_name, version)
        self.environments.append(env)
        self._update_env_list()

    def call_provision_terraform(self, env_name):
        """Call terraform apply on the environment."""
        env = self.get_environment(env_name)
        if self.config.get('terraform_command', False):
            print self._terraform(env, "apply")

    def call_provision_kubernetes(self, env_name):
        """Create Kubernetes components according to environment specification."""
        env = self.get_environment(env_name)
        if self.config.get('kubectl_command', False):
            print self._kubectl("create namespace %s" % env.get_name())

            for cmd in self.config['kubeinit']:
                print self._kubectl("--namespace %s %s" % (env.get_name(), cmd))

            for c in env.get_components():
                if c.get_type() == 'kube':
                    print "Provisioning kubernetes component %s" % c.get_name()
                    print self._kubectl("create -f -", input=open(c.get_file(), 'r'))

    def call_provision_environment(self, env_name):
        """Do initial provisioning of an environment in Kubernetes and Terraform."""
        self.call_provision_terraform(env_name)
        self.call_provision_kubernetes(env_name)
        self.call_create_endpoints(env_name)

    def call_recreate_component(self, env_name, component_name):
        """Delete and (re-)create and component in an environment."""
        comp = self.get_environment(env_name).get_component(component_name)

        try:
            print self._kubectl("delete -f -", input=open(comp.get_file(), 'r'))
        except:
            pass
        print self._kubectl("create -f -", input=open(comp.get_file(), 'r'))

    def call_refresh_environment(self, env_name):
        """Refresh the environment specification for the specified environment."""
        env = self.get_environment(env_name)
        self._update_env_specs()
        env.refresh_spec()
        return self.call_get_spec_version(env_name)

    def call_teardown_environment(self, env_name):
        """Delete environment resources from Kubernetes and Terraform."""
        env = self.get_environment(env_name)
        if self.config.get('kubectl_command', False):
            try:
                print self._kubectl("delete namespace %s" % env.get_name())
            except:
                pass
        if self.config.get('terraform_command', False):
            print self._terraform(env, "destroy -force")

        self.call_remove_endpoints(env.name)

    def call_get_image_tag(self, env_name, component_name):
        """Return the image tag for a specified component."""
        env = self.get_environment(env_name)
        comp = env.get_component(component_name)
        return comp.get_image_tag()

    def call_get_image_name(self, env_name, component_name):
        env = self.get_environment(env_name)
        comp = env.get_component(component_name)
        return comp.get_image_name()

    def call_update_component(self, env_name, component_name, image_tag):
        """Update a component with a new image tag."""
        env = self.get_environment(env_name)
        comp = env.get_component(component_name)
        comp.set_image_tag(image_tag)
        self._kubectl("--namespace=%s rolling-update %s --image=%s" % (env.get_name(),
                                                                       comp.get_name(),
                                                                       comp.get_image_name()))

    def call_create_endpoints(self, env_name):
        """Create DNS endpoints for an environment."""
        if not self.endpoint_zone:
            return False
        env = self.get_environment(env_name)
        for c in env.get_components(resource_type='kube'):
            spec = c.get_spec()
            if spec['kind'] != 'Service':
                continue
            try:
                if spec['spec']['type'] != 'LoadBalancer':
                    continue
            except:
                continue
            elb = self._kubectl("--namespace=%s describe svc %s|grep Ingress|awk '{print $3}'" % (env.get_name(), spec['metadata']['name']))
            endpoint = "%s.%s.%s" % (spec['metadata']['name'], env.get_name(), self.config.get('endpoint_zone'))
            if self.valid_ip(elb):
                rr, change_info = self.endpoint_zone.create_a_record(endpoint, [elb])
            else:
                rr, change_info = self.endpoint_zone.create_cname_record(endpoint, [elb])
            print "Created endpoint: %s" % endpoint

        if self.config.get('terraform_command', False):
            for o in self._terraform(env, "output", add_credentials=False).split("\n"):
                if len(o) > 1:
                        name, target = [s.strip() for s in o.split('=')]
                        endpoint = "%s.%s.%s" % (name, env.get_name(), self.config.get('endpoint_zone'))
                        rr, change_info = self.endpoint_zone.create_cname_record(endpoint, [target])
                        print "Created endpoint: %s" % endpoint

    def call_remove_endpoints(self, env_name):
        """Delete DNS endpoints for an environment."""
        if not self.endpoint_zone:
            return False
        env = self.get_environment(env_name)
        env_fqdn = "%s.%s" % (env.get_name(), self.config.get('endpoint_zone'))

        for r in self.endpoint_zone.record_sets:
            if len(env_fqdn) <= len(r.name) and r.name[-len(env_fqdn):] == env_fqdn:
                print "Deleting endpoint: %s" % r.name
                r.delete()

    def call_list_endpoints(self, env_name):
        """Return a list of DNS endpoints for an environment."""
        if not self.endpoint_zone:
            return False
        env = self.get_environment(env_name)
        env_fqdn = "%s.%s" % (env.get_name(), self.config.get('endpoint_zone'))

        for r in self.endpoint_zone.record_sets:
            if len(env_fqdn) <= len(r.name) and r.name[-len(env_fqdn):] == env_fqdn:
                print "Endpoint: %s" % r.name

    def call_get_logs(self, env_name, component_name=None, pod_name=None):
        """Return logs for a pod in a component."""
        if not component_name and not pod_name:
            return "Need to specify either component name or pod name."
        if pod_name:
            return self._kubectl("--namespace=%s logs %s" % (env_name, pod_name))
        pods = self._kubectl("--namespace=%s get po -l app=%s | awk '{print $1}'" % (env_name, component_name)).split("\n")[1:-1]
        if len(pods) == 1:
            return self._kubectl("--namespace=%s logs %s" % (env_name, pods[0]))
        if len(pods) < 1:
            return "No pods found for component %s in %s" % (component_name, env_name)
        return "Component %s has %d pods, please specify explicitly with --pod-name\nPods: %s" % (component_name, len(pods), ", ".join(pods))

    def call_get_spec_version(self, env_name):
        """Returns the specification version of a running environment."""
        env = self.get_environment(env_name)
        if self.config.get('spec_use_git', False):
            return env.get_version() + ": " + subprocess.check_output("cd %s && git --no-pager log -1 --format='%%an at %%ci %%s'" % self.config.get('spec_dir'), shell=True)
        return env.get_version()

    def __get_environment_list(self):
        env_list = []

        for i in os.listdir("environments/"):
            if not os.path.isdir("environments/" + i):
                continue
            env_list.append(Environment(i, self.__read_env_version(i)))
        return env_list

    def __get_kube_environment_list(self):
        return [{'name': env.split(" ")[0], 'version': env.split(" ")[1]}
                for env in self._kubectl("get namespaces -L env_version"
                                         "awk '{ print $1,$4 }' | "
                                         "tail -n+2 | "
                                         "grep -v default | "
                                         "grep -v kube-system"
                                         ).split("\n") if ' ' in env]

    def _get_config(self, key):
        return self.config.get(key, False)

    def __read_env_version(self, env_name):
        with open("environments/" + env_name + "/VERSION", 'r') as f:
            return f.readline()

    def _kubectl(self, cmd, input=None):
        return subprocess.check_output(
            "%s %s" %
            (self.config.get('kubectl_command'), cmd), shell=True, stdin=input)

    def _terraform(self, env, cmd, add_credentials=True):
        return subprocess.check_output("cd %s && %s %s %s" % (
                                       env.get_env_dir(),
                                       self.config.get('terraform_command', 'terraform'),
                                       cmd,
                                       "-var 'aws_access_key=" + self.config.get('aws_access_key') + "' -var 'aws_secret_key=" + self.config.get('aws_secret_key') + "' " if add_credentials else ""),
                                       shell=True)

    def _update_env_specs(self):
        if not self.config.get('spec_use_git', False):
            return

        if os.path.isdir("%s/" % self.config.get('spec_dir')):
            print subprocess.check_output("cd %s && git pull" % self.config.get('spec_dir'), shell=True)
        else:
            print subprocess.check_output("git clone %s %s" % (self.config.get('spec_repo'), self.config.get('spec_dir')), shell=True)

    def _update_env_list(self):
        self.environments = self.__get_environment_list()

    def __log(self, message):
        if self.config.get('log_stdout', False):
            print log_message


class Environment(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version.strip()
        self.components = []

        if not os.path.isdir(self.get_env_dir()):
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

    def refresh_spec(self):
        self.__make_spec()

    def get_components(self, resource_type=''):
        if not resource_type:
            return self.components
        else:
            return [c for c in self.components if c.get_type() == resource_type]

    def __make_spec(self):
        preserved_component_images = []

        if os.path.isdir("environments/" + self.name):
            # we are refreshing the environment specs
            print "Refreshing environment spec from %s" % self.get_skel_dir()

            for c in self.get_components(resource_type='kube'):
                if c.get_image_basename():
                    preserved_component_images.append({
                        'name': c.get_name(),
                        'image': c.get_image_basename(),
                        'image_tag': c.get_image_tag()
                        })
            shutil.rmtree(self.get_env_dir())
        else:
            print "Copying environment spec from %s" % self.get_skel_dir()

        os.mkdir(self.get_env_dir())

        for i in os.listdir(self.get_skel_dir()):
            file_path = os.path.join(self.get_skel_dir(), i)
            if not os.path.isfile(file_path):
                continue
            env_file_path = os.path.join(self.get_env_dir(), i)
            with open(file_path, 'r') as s, open(env_file_path, 'w') as t:
                for line in s:
                    t.write(line.replace("%%ENV_NAME%%", self.name))

            with open(os.path.join(self.get_env_dir(), "VERSION"), 'w') as f:
                f.write(self.version + "\n")

            comp = self.__gen_component(env_file_path)
            self.components.append(comp)

        for p in preserved_component_images:
            c = self.get_component(p['name'])
            if c.get_image_basename() != p['image']:
                print "Not preserving image tag for %s, as image has changed (new: %s)" % (c.get_name(), c.get_image_basename())
                continue
            print "Preserved %s image tag as %s" % (c.get_name(), p['image_tag'])
            c.set_image_tag(p['image_tag'])

    def __read_spec(self):
        for i in os.listdir(self.get_env_dir()):
            file_path = os.path.join(self.get_env_dir(), i)
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

    def get_skel_dir(self):
        return "%s/%s" % ("skeletons", self.version)

    def get_env_dir(self):
        return "environments/%s" % self.name

    def __repr__(self):
        return self.__str__()

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

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.name + " [" + self.type + "]"
