#!/bin/bash

# required for ease of development
pushd /solar
python setup.py develop
popd

pushd /solard
python setup.py develop
popd

#used only to start celery on docker
ansible-playbook -v -i "localhost," -c local /celery.yaml --skip-tags slave,stop

tail -f /var/run/celery/*.log
