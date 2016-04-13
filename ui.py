from artemis.tool import Artemis
from threading import Thread
from flask import Flask, render_template


def async(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper


tool = Artemis(config_file='config.yml')

ui = Flask("artemis")
ui.config.update(
    DEBUG=True,
    SECRET_KEY='abc'
)

@async
def call_image_update(env_name, component_name, image_tag):
    tool.update_component(env_name, component_name, image_tag)

@ui.route('/')
def list_environments():
    return render_template("list_environments.html", envs=tool.get_environments())

@ui.route('/env/<env>')
def show_environment(env):
    return render_template("show_environment.html", env=tool.get_environment(env), tool=tool)

@ui.route('/update/<env_name>/<component_name>/<image_tag>')
def update_image(env_name, component_name, image_tag):
    call_image_update(env_name, component_name, image_tag)
    return "Request processing"

ui.run(host='0.0.0.0')
