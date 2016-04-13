# Artemis
Tool to manage environments with Kubernetes and Terraform. WIP

Environment specifications should be stored in a repository set in the configuration variable 'spec_repo'.

The specifications can include:
- terraform specification files in ```spec_repo/<version>/*.tf``` (WIP)
- kubernetes resource files in ```spec_repo/<version>/*.yaml```

Artemis makes no effort to authenticate to pull the repo -- currently we merely run ```git clone $spec_repo```, or ```git pull``` if the directory exists.


Created environments are stored in ```environments/<environment_name>```.

Installation in a virtualenv:
```
git clone git@github.com:project-ada/artemis.git
cd artemis
virtualenv .
source bin/activate
pip install -r requirements.txt
vim config.yml
```

To create an environment from a specification:
```
python cli.py create test-env 1.0
```

To build environment in Kubernetes:
```
python cli.py build test-env
```

To list created environments:
```
python cli.py list-envs
```

To list components in an environment:
```
python cli.py list-comp <environment_name>
```

To update an image tag in a component:
```
python cli.py set-image-tag <environment_name> <component_name> <new_image_tag>
# ie.
python cli.py set-image-tag test-env my-nginx-rc latest
```

To destroy environment in Kubernetes:
```
python cli.py teardown test-env
```

To run a rudimentary flask-based UI:
```
python ui.py
```
