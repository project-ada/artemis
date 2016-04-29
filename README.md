# Artemis
Tool to manage environments with Kubernetes and Terraform. WIP

Environment specifications should be stored in a directory set in the configuration variable 'spec_dir'. Optionally, you can set 'spec_repo' to a git repository, and set 'spec_use_git' to true.

The specifications can include:
- terraform specification files in ```spec_dir/<version>/*.tf``` (WIP)
- kubernetes resource files in ```spec_dir/<version>/*.yaml```

Artemis makes no effort to authenticate to pull the repo if spec_use_git is true -- currently we merely run ```git clone $spec_repo```, or ```git pull``` if the directory exists.

Created environments are stored in ```environments/<environment_name>```.

If the configuration variable ```endpoint_zone``` is defined, Artemis will attempt to use the AWS credentials to create Route53 CNAME records for every Service[type=LoadBalancer] defined in the kubernetes resource files. The records will be removed on teardown. Please note that ```endpoint_zone``` must be a FQDN with the trailing dot, ie. ```endpoint_zone: "my-domain.com."```.

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
For available commands:
```
python cli.py help
```
## Examples
Assuming we have an environment specification in ```spec_dir/1.0/```, we can create a new environment:
```
python cli.py create-environment --env-name=int01 --version=1.0
```

To build environment in Kubernetes:
```
python cli.py provision-environment --env-name=int01
```

To list created environments:
```
python cli.py list-environments
```

To list components in an environment:
```
python cli.py list-components --env-name=int01
```

To update a component with a new image tag:
```
python cli.py update-component --env-name=int01 --component-name=my-nginx-rc --image-tag=latest
```

To destroy environment's resources in Kubernetes and Terraform:
```
python cli.py teardown-environment --env-name=int01
```

To run a rudimentary flask-based UI:
```
python ui.py
```

## Roadmap
- refactor Artemis, Environment and Component classes
- DRY for cli.py and ui.py: the logic for CLI commands and Flask endpoints should be in a single place, either by introspecting the Artemis class or separately defining a single list of methods and arguments, which is used by both to generate endpoints
