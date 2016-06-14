from artemis.tool import Artemis
from threading import Thread
from flask import Flask, render_template, request
import requests
import simplejson as json
import logging
from logging.handlers import RotatingFileHandler


def async(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper


tool = Artemis(config_file='config.yml')

ui = Flask("artemis-ui")
ui.config.update(
    DEBUG=True,
    SECRET_KEY='abc'
)


@async
def call_image_update(env_name, component_name, image_tag):
    tool.update_component(env_name, component_name, image_tag)

@async
def call_recreate_component(env, component):
    tool.call_recreate_component(env, component)

@ui.route('/')
def list_environments():
    return render_template("list_environments.html",
                           envs=tool.get_environments())


@ui.route('/env/<env_name>')
def show_environment(env_name):
    env = tool.get_environment(env_name)
    pod_list = tool._kubectl("--namespace=%s get pods -L app" % env.get_name()).split("\n")
    components = []
    for pod in pod_list[1:-1]:
        pod_data = pod.split()
        component = None
        for c in env.get_components():
            if c.get_name() == pod_data[5]:
                component = c
        if component is None:
            continue
        components.append({
            'name': component.get_name(),
            'image_name': component.get_image_basename(),
            'image_tag': component.get_image_tag(),
            'env': env,
            'uptime': pod_data[4],
            'pod_name': pod_data[0],
            'status': pod_data[2]
                })

    return render_template("show_environment.html",
                           components=components,
                           env=env, spec_version=tool.call_get_spec_version(env_name=env_name))


@ui.route('/call/<method_name>')
def call_method(method_name):
    try:
        method = getattr(tool, "call_" + method_name.replace("-", "_"))
        args = { k: v for k, v in (request.form if request.method == 'POST' else request.args.items())}
    except:
        return "Invalid request"
    
    return "<pre>%s</pre>" % str(method(**args)).replace("<","&lt;")

@ui.route('/update/<env_name>/<component_name>/<image_tag>')
def update_image(env_name, component_name, image_tag):
    call_image_update(env_name, component_name, image_tag)
    return "Request processing"


@ui.route('/recreate/<env_name>/<component_name>')
def recreate_component(env_name, component_name):
    env = tool.get_environment(env_name)
    component = env.get_component(component_name)
    tool.call_recreate_component(env_name, component_name)
    return "Recreated"

@ui.route('/newimage/<image_vendor>/<image_name>/<branch_name>/<build_number>')
def new_image_version(image_vendor, image_name, branch_name, build_number):
    updated_environments = []
    for env in tool.get_environments():
        for component in env.get_components(resource_type='kube'):
            if component.get_image_basename() != image_vendor + "/" + image_name:
                continue
            try:
                component_branch, component_tag = component.get_image_tag().split("-")
            except:
                continue
            if component_branch != branch_name or component_tag != 'latest':
                continue
            print "Updating %s %s with %s" % (env.get_name(), component.get_name(), component.get_image_tag())
            call_recreate_component(env.get_name(), component.get_name())
            updated_environments.append(env.get_name())

    if tool._get_config('slack_notification_webhook') and updated_environments:
        msg = {
            'username': 'artemis',
            'text': "Component '%s' is being updated in environment%s %s" % (image_name,
                                                                        's:' if len(updated_environments) > 1 else '',
                                                                        ', '.join(updated_environments))
        }
        r = requests.post(tool._get_config('slack_notification_webhook'), data=json.dumps(msg))
        print r
    return "OK"

if __name__ == '__main__':
    handler = RotatingFileHandler('artemis-ui.log', maxBytes=20971520, backupCount=5)
    handler.setLevel(logging.INFO)
    ui.logger.addHandler(handler)
    ui.run(host='0.0.0.0')
