from artemis.tool import Artemis
from threading import Thread
from flask import Flask, render_template


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
                           env=env)


@ui.route('/logs/<env_name>/<pod_name>')
def logs(env_name, pod_name):
    return render_template("stdout.html", stdout=tool._kubectl("--namespace=%s logs %s" % (env_name, pod_name)))


@ui.route('/update/<env_name>/<component_name>/<image_tag>')
def update_image(env_name, component_name, image_tag):
    call_image_update(env_name, component_name, image_tag)
    return "Request processing"


ui.run(host='0.0.0.0')
