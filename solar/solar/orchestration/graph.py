#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import uuid

import networkx as nx

from solar import utils
from .traversal import states

from solar.interfaces import orm
from solar.interfaces.db import get_db

db = get_db()


def save_graph(graph):
    # maybe it is possible to store part of information in AsyncResult backend
    orm.DBGraph.create(graph)


def get_graph(uid):
    return orm.DBGraph.load(uid).graph


get_plan = get_graph


def parse_plan(plan_path):
    """ parses yaml definition and returns graph
    """
    plan = utils.yaml_load(plan_path)
    dg = nx.MultiDiGraph()
    dg.graph['name'] = plan['name']
    for task in plan['tasks']:
        defaults = {
            'node_name': task['uid'],
            'status': 'PENDING',
            'errmsg': None,
            }
        defaults.update(task['parameters'])
        dg.add_node(
            task['uid'], **defaults)
        for v in task.get('before', ()):
            dg.add_edge(task['uid'], v)
        for u in task.get('after', ()):
            dg.add_edge(u, task['uid'])
    return dg


def create_plan_from_graph(dg, save=True):
    dg.graph['uid'] = "{0}:{1}".format(dg.graph['name'], str(uuid.uuid4()))
    if save:
        save_graph(dg)
    return dg


def show(uid):
    dg = get_graph(uid)
    result = {}
    tasks = []
    result['uid'] = dg.graph['uid']
    result['name'] = dg.graph['name']
    for n in nx.topological_sort(dg):
        data = dg.node[n]
        tasks.append(
            {'uid': n,
             'parameters': data,
             'before': dg.successors(n),
             'after': dg.predecessors(n)
             })
    result['tasks'] = tasks
    return utils.yaml_dump(result)


def create_plan(plan_path, save=True):
    """
    """
    dg = parse_plan(plan_path)
    return create_plan_from_graph(dg, save=save)


def update_plan(uid, plan_path):
    """update preserves old status of tasks if they werent removed
    """

    new = parse_plan(plan_path)
    old = get_graph(uid)
    return update_plan_from_graph(new, old).graph['uid']


def update_plan_from_graph(new, old):
    new.graph = old.graph
    for n in new:
        if n in old:
            new.node[n]['status'] = old.node[n]['status']

    save_graph(new)
    return new


def reset_by_uid(uid, state_list=None):
    dg = get_graph(uid)
    return reset(dg, state_list=state_list)


def reset(graph, state_list=None):
    for n in graph:
        if state_list is None or graph.node[n]['status'] in state_list:
            graph.node[n]['status'] = states.PENDING.name
    save_graph(graph)


def reset_filtered(uid):
    reset_by_uid(uid, state_list=[states.SKIPPED.name, states.NOOP.name])


def report_topo(uid):

    dg = get_graph(uid)
    report = []

    for task in nx.topological_sort(dg):
        data = dg.node[task]
        report.append([
            task,
            data['status'],
            data['errmsg'],
            data.get('start_time'),
            data.get('end_time')])

    return report
