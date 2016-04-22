# Artemis
Tool to manage environments with Kubernetes and Terraform. WIP

Environment specifications should be stored in a directory set in the configuration variable 'spec_dir'. Optionally, you can set 'spec_repo' to a git repository, and set 'spec_use_git' to true.

The specifications can include:
- terraform specification files in ```spec_dir/<version>/*.tf``` (WIP)
- kubernetes resource files in ```spec_dir/<version>/*.yaml```

Artemis makes no effort to authenticate to pull the repo if spec_use_git is true -- currently we merely run ```git clone $spec_repo```, or ```git pull``` if the directory exists.

Created environments are stored in ```environments/<environment_name>```.

If the configuration variable ```endpoint_zone``` is defined, Artemis will attempt to create CNAME records for every Service[type=LoadBalancer] defined in the kubernetes resource files. The records will be removed on teardown. Please note that ```endpoint_zone``` must be a FQDN with the trailing dot, ie. ```endpoint_zone: "my-domain.com."```.

## Assumptions
- Docker images are pushed to a repository with the tag ```<branch_name>-<build_number>``` and ```<branch_name>-latest```.
- Currently, the only supported Kubernetes 'component' is a ReplicationController

## Installation
Installation in a virtualenv:
```
git clone git@github.com:project-ada/artemis.git
cd artemis
virtualenv .
source bin/activate
pip install -r requirements.txt
vim config.yml
```

## Quick start
To create an environment from a specification:
```
python cli.py create <environment_name> <spec_version>
# ie.
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
python cli.py list-components <environment_name>
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
