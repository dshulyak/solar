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


__all__ = ['add_dep', 'add_react', 'add_events', 'Dep', 'React']

import networkx as nx

from solar import core
from solar.core.log import log
from solar.interfaces.db import get_db
from solar.events.controls import Dep, React, StateChange

db = get_db()


def create_event(event_dict):
    etype = event_dict.pop('etype')
    if etype == React.etype:
        return React(**event_dict)
    elif etype == Dep.etype:
        return Dep(**event_dict)
    else:
        raise Exception('No support for type %s', etype)

def set_events(name, lst):
    db.save(
        name,
        [i.to_dict() for i in lst],
        collection=db.COLLECTIONS.events)


def add_event(ev):
    rst = all_events(ev.parent_node)
    if ev in rst: return

    rst.append(ev)
    set_events(ev, rst)


def maybe_resource(name):
    if isinstance(name, core.resource.Resource):
        return res.name
    else:
        return name

def add_dep(parent, dep, actions, state='success'):

    for act in actions:
        d = Dep(maybe_resource(parent), act, state=state,
                depend_node=maybe_resource(dep), depend_action=act)
        add_event(d)
        log.debug('Added event: %s', d)


def add_react(parent, dep, actions, state='success'):
    for act in actions:
        r = React(maybe_resource(parent), act, state=state,
                  depend_node=maybe_resource(dep), depend_action=act)
        add_event(r)
        log.debug('Added event: %s', r)


def set_events(resource, lst):
    db.create(
        resource,
        [i.to_dict() for i in lst],
        collection=db.COLLECTIONS.events)


def remove_event(ev):
    rst = all_events(ev.parent_node)
    set_events(ev.parent_node, [it for it in rst if not it == ev])


def remove_event(ev):
    rst = all_events(ev.parent_node)
    set_events(ev.parent_node, [i.to_dict() for i in rst if i != ev])


def add_events(name, lst):
    rst = all_events(name)
    for ev in lst:
        if ev not in rst:
            rst.append(ev)
    set_events(name, rst)


def all_events(resource):
    events = db.get(resource, collection=db.COLLECTIONS.events,
                    return_empty=True, db_convert=False)
    if not events:
        return []
    return [create_event(i) for i in events.properties]


def bft_events_graph(start):
    """Builds graph of events traversing events in breadth-first order
    This graph doesnt necessary reflect deployment order, it is used
    to show dependencies between resources
    """
    dg = nx.DiGraph()
    stack = [start]
    visited = set()

    while stack:
        item = stack.pop()
        current_events = all_events(item)

        for ev in current_events:
            dg.add_edge(ev.parent, ev.dependent, label=ev.state)

            if ev.depend_node in visited:
                continue

            # it is possible to have events leading to same resource but
            # different action
            if ev.depend_node in stack:
                continue

            stack.append(ev.depend_node)
        visited.add(ev.parent_node)
    return dg



def build_edges(changed_resources, changes_graph, events):
    """
    :param changed_resources: list of resource names that were changed
    :param changes_graph: nx.DiGraph object with actions to be executed
    :param events: {res: [controls.Event objects]}
    """
    stack = changed_resources[:]
    visited = []
    while stack:
        node = stack.pop()

        if node in events:
            log.debug('Events %s for resource %s', events[node], node)
        else:
            log.debug('No dependencies based on %s', node)

        if node not in visited:
            for ev in events.get(node, ()):
                ev.insert(stack, changes_graph)

        visited.append(node)
    return changes_graph
