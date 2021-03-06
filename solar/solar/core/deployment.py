# Deploying stuff from YAML definition

import os
import shutil
import yaml

from solar.core import db
from solar.core.log import log
from solar.core import resource as xr
from solar.core import signals as xs


def deploy(filename):
    with open(filename) as f:
        config = yaml.load(f)

    workdir = config['workdir']
    resource_save_path = os.path.join(workdir, config['resource-save-path'])

    # Clean stuff first
    db.clear()
    xs.Connections.clear()
    shutil.rmtree(resource_save_path, ignore_errors=True)
    os.makedirs(resource_save_path)

    # Create resources first
    for resource_definition in config['resources']:
        name = resource_definition['name']
        model = os.path.join(workdir, resource_definition['model'])
        args = resource_definition.get('args', {})
        log.debug('Creating %s %s %s %s', name, model, resource_save_path, args)
        xr.create(name, model, resource_save_path, args=args)

    # Create resource connections
    for connection in config['connections']:
        emitter = db.get_resource(connection['emitter'])
        receiver = db.get_resource(connection['receiver'])
        mapping = connection.get('mapping')
        log.debug('Connecting %s %s %s', emitter.name, receiver.name, mapping)
        xs.connect(emitter, receiver, mapping=mapping)

    # Run all tests
    if 'test-suite' in config:
        log.debug('Running tests from %s', config['test-suite'])
        test_suite = __import__(config['test-suite'], {}, {}, ['main'])
        test_suite.main()
