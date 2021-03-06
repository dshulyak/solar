import copy
import io
import os

import yaml

from solar.extensions import base
from solar import utils


class Discovery(base.BaseExtension):

    VERSION = '1.0.0'
    ID = 'discovery'
    PROVIDES = ['nodes_resources']

    COLLECTION_NAME = 'nodes'

    FILE_PATH = os.path.join(
        utils.read_config()['examples-dir'],
        'nodes_list.yaml'
    )

    def discover(self):
        nodes_to_store = []
        with io.open(self.FILE_PATH) as f:
            nodes = yaml.load(f)

        for node in nodes:
            exist_node = self.db.get_record(self.COLLECTION_NAME, node['id'])
            if not exist_node:
                node['tags'] = ['node/{0}'.format(node['id'])]
                nodes_to_store.append(node)

        self.db.store_list(self.COLLECTION_NAME, nodes_to_store)

    def nodes_resources(self):
        nodes_list = self.db.get_list(self.COLLECTION_NAME)
        nodes_resources = []

        for node in nodes_list:
            node_resource = copy.deepcopy(node.get('attrs', {}))
            node_resource['id'] = node['id']
            node_resource['name'] = node['id']
            node_resource['handler'] = 'data'
            node_resource['type'] = 'resource'
            node_resource['version'] = self.VERSION
            node_resource['tags'] = node['tags']
            node_resource['input'] = node
            node_resource['ip'] = node['ip']
            node_resource['ssh_user'] = node['ssh_user']
            node_resource['ssh_private_key_path'] = node['ssh_private_key_path']

            nodes_resources.append(node_resource)

        return nodes_resources
