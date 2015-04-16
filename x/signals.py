# -*- coding: UTF-8 -*-
from collections import defaultdict

import db

from x import utils


CLIENTS_CONFIG_KEY = 'clients-data-file'
CLIENTS = utils.read_config_file(CLIENTS_CONFIG_KEY)


def connect(emitter, reciver, mappings):
    for src, dst in mappings:
        CLIENTS.setdefault(emitter.name, {})
        CLIENTS[emitter.name].setdefault(src, [])
        CLIENTS[emitter.name][src].append((reciver.name, dst))

    utils.save_to_config_file(CLIENTS_CONFIG_KEY, CLIENTS)


def notify(source, key, value):
    if key in CLIENTS[source.name]:
        for client, r_key in CLIENTS[source.name][key]:
            resource = db.get_resource(client)
            if resource:
                resource.update({r_key: value})
            else:
                #XXX resource deleted?
                pass


def assign_connections(reciver, connections):
    mappings = defaultdict(list)
    for key, dest in connections.iteritems():
        resource, r_key = dest.split('.')
        resource = db.get_resource(resource)
        value = resource.args[r_key]
        reciver.args[key] = value
        mappings[resource].append((r_key, key))
    for resource, r_mappings in mappings.iteritems():
        connect(resource, reciver, r_mappings)


def connection_graph():
    resource_dependencies = {}

    for source, destinations in CLIENTS.items():
        resource_dependencies[source] = [
            destination[0] for destination in destinations
        ]

    return resource_dependencies
