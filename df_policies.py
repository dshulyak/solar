#!/usr/bin/env python
"""
Q/A
1. What is operation?
Solar client/api action
2. What is rule?
Condition, based on which we produce operations.
Condition should work only with local data, passing correct data will
be responsibility of fuel or solar


TODO
1. add topological sort for operations
2. reuse fuel dsl for conditions in order to integrate faster
"""

import click
import yaml
from functools import wraps
import networkx as nx


class Operation(object):

    @property
    def operation(self):
        return self.__class__.__name__.upper()

    @property
    def identity(self):
        return '%s_%s' % (self.operation, self.uid)


class Add(Operation):

    @property
    def inverse(self):
        return Remove(self.uid)

    def __init__(self, resource, uid, parameters=None):
        self.resource = resource
        self.uid = uid
        self.parameters = parameters or {}

    def __repr__(self):
        return '{} resource={} uid={} {}'.format(
            self.__class__.__name__.upper(), self.resource,
            self.uid,
            self.parameters)

    def __eq__(self, other):
        return all(
            (self.__class__.__name__ == other.__class__.__name__,
             self.resource == other.resource,
             self.uid == other.uid))

    def __hash__(self):
        return hash((self.__class__.__name__, self.resource, self.uid))


class Update(Operation):

    def __init__(self, uid, parameters):
        self.uid = uid
        self.parameters = parameters

    def __repr__(self):
        return '{} uid={} {}'.format(
            self.__class__.__name__.upper(), self.uid,
            self.parameters)

    def __hash__(self):
        return hash((self.__class__.__name, self.uid))


class Remove(Add):

    def __init__(self, uid):
        self.uid = uid

    def __repr__(self):
        return '{} uid={}'.format(
            self.__class__.__name__.upper(),
            self.uid)


class Connect(Operation):

    @property
    def inverse(self):
        return Disconnect(self.emitter, self.subscriber, self.parameters)

    def __init__(self, emitter, subscriber, parameters=None):
        self.emitter = emitter
        self.subscriber = subscriber
        self.parameters = parameters or {}

    def __repr__(self):
        return '{} from={} to={} {}'.format(
            self.__class__.__name__.upper(), self.emitter, self.subscriber, self.parameters)

    def __hash__(self):
        return hash(
            (self.__class__.__name__, self.emitter, self.subscriber))

    @property
    def uid(self):
        return '%s_%s' % (self.emitter, self.subscriber)


class Disconnect(Connect):

    @property
    def inverse(self):
        return Connect(self.emitter, self.subscriber, self.mapping)


STAGED = yaml.load("""
env: 2
nodes:
    - name: node1
      role: controller
      uid: 1
    - name: node2
      role: compute
      uid: 2
swift:
    enabled: true
    ring_size: 256
ceph:
    enabled: false
""")


UPDATED = yaml.load("""
env: 2
nodes:
    - name: node1
      role: controller
      uid: 1
    - name: node2
      role: compute
      uid: 2
swift:
    enabled: true
    ring_size: 512
ceph:
    enabled: false
""")


COMMITTED = yaml.load("""
env: 2
nodes:
    - name: node1
      role: controller
      uid: 1
    - name: node1
      role: ceph-osd
      uid: 1
    - name: node2
      role: compute
      uid: 2
swift:
    enabled: false
    ring_size: 256
ceph:
    enabled: true
""")


RULES = {}

def rule(conflict=()):
    def add_rule(func):
        global RULES
        RULES[func.__name__] = [func, conflict]
        @wraps(func)
        def _wrap(*args, **kwargs):
            return func(*args, **kwargs)
        return _wrap
    return add_rule


@rule()
def nodes(data):
    for node in data.get('nodes', ()):
        yield Add('node',
                  'node.%s' % node['uid'],
                  {'name': node['name'],
                   'env': data['env']})


@rule()
def roles(data):
    for node in data.get('nodes', ()):
        uid = '%s.%s' % (node['role'], node['uid'])
        yield Add(node['role'], uid)
        yield Connect('node.%s' % node['uid'], uid)


@rule(conflict=('ceph',))
def swift(data):
    if data['swift']['enabled']:
        controllers = filter(
            lambda x: x['role'] == 'controller',
            data['nodes'])
        for controller in controllers:
            yield Add('swift', 'swift.%s' % controller['uid'],
                      {'ring_size': data['swift']['ring_size']})
            yield Connect(
                'node.%s' % controller['uid'],
                'swift.%s' % controller['uid'])


@rule(conflict=('swift',))
def ceph(data):
    if data['ceph']['enabled']:
        controllers = filter(
            lambda x: x['role'] == 'controller',
            data['nodes'])
        computes = filter(
            lambda x: x['role'] == 'computes',
            data['nodes'])
        for controller in controllers:
            yield Add(
                'ceph_controller',
                'ceph_controller.%s' % controller['uid'])
            yield Connect(
                'node.%s' % controller['uid'],
                'ceph_controller.%s' % controller['uid'])
        for compute in computes:
            yield Add(
                'ceph_compute',
                'ceph_compute.%s' % compute['uid'])
            yield Connect(
                'node.%s' % compute['uid'],
                'ceph_compute.%s' % compute['uid'])


@click.group()
def main():
    pass


@main.command()
def staged():
    for rule, conflicts in RULES.values():
        for operation in rule(STAGED):
            print operation


@main.command()
def committed():
    for rule, conflicts in RULES.values():
        for operation in rule(COMMITTED):
            print operation


@main.command()
def rules():
    for rule in RULES:
        print 'rule=%s conflicts=%s' % (rule, RULES[rule][1])


def build(operations):
    dg = nx.DiGraph()

    for operation in operations:
        dg.add_node(operation.identity, operation=operation)

    for op in dg.nodes():
        operation = dg.node[op]['operation']

        if isinstance(operation, Connect):
            dg.add_edge(
                'ADD_%s' % operation.emitter,
                operation.identity)
            dg.add_edge(
                'ADD_%s' % operation.subscriber,
                operation.identity)
        elif isinstance(operation, Update):
            dg.add_edge(
                'ADD_%s' % operation.uid, operation.identity)
        elif isinstance(operation, Disconnect):
            dg.add_edge(
                operation.identity,
                'REMOVE_%s' % operation.emitter)
            dg.add_edge(
                operation.identity,
                'REMOVE_%s' % operation.subscriber)
    return dg


@main.command()
@click.option('-s', default=False, is_flag=True)
@click.option('-c', default=False, is_flag=True)
def topo(s, c):
    if s:
        rst = map(lambda r: r[0](STAGED), RULES.values())
    elif c:
        rst = map(lambda r: r[0](COMMITTED), RULES.values())
    dg = build([op for ops in rst for op in ops])
    for op in nx.topological_sort(dg):
        print dg.node[op]['operation']



@main.command()
@click.option('-s', default=False, is_flag=True)
@click.option('-c', default=False, is_flag=True)
@click.option('-u', default=False, is_flag=True)
def diff(s, c, u):
    #todo remove this duplication
    if c:
        crules = map(lambda r: r[0](COMMITTED), RULES.values())
        cops_hash = {}
        for rule in crules:
            for o in rule:
                cops_hash[o] = o
    elif u:
        crules = map(lambda r: r[0](UPDATED), RULES.values())
        cops_hash = {}
        for rule in crules:
            for o in rule:
                cops_hash[o] = o
    else:
        cops_hash = {}

    if s:
        srules = map(lambda r: r[0](STAGED), RULES.values())
        sops_hash = {}
        for rule in srules:
            for o in rule:
                sops_hash[o] = o
    else:
        sops_hash = {}
    rst = []
    for operation in set(cops_hash.keys() + sops_hash.keys()):
        cop = cops_hash.get(operation)
        sop = sops_hash.get(operation)
        if sop and not cop:
            rst.append(sop)
        elif cop and not sop:
            rst.append(cop.inverse)
        else:
            if cop.parameters != sop.parameters:
                rst.append(
                    Update(sop.uid, sop.parameters))
    dg = build(rst)
    for op in nx.topological_sort(dg):
        if 'operation' in dg.node[op]:
            print dg.node[op]['operation']



if __name__ == '__main__':
    main()
