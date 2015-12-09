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

from contextlib import contextmanager
import time

from solar.dblayer.solar_models import Lock as DBLock


class Lock(object):

    def __init__(self, uid, identity, retries=0, wait=10):
        """
        :param uid: target of lock
        :param identity: unit of concurrency
        :param retries: retries of acquiring lock
        :param wait: sleep between retries
        """
        self.uid = uid
        self.identity = identity
        self.retries = retries
        self.wait = wait

    @classmethod
    def _acquire(cls, uid, identity):
        try:
            lk = DBLock.from_dict(uid, {'identity': identity})
            lk.save()
            # we should have another exception for siblings
        except RuntimeError:
            siblings = []
            for s in lk._riak_object.siblings:
                if s.data.get('identity') != identity:
                    siblings.append(s)
            lk._riak_object.siblings = siblings
            lk.save()
        return lk

    @classmethod
    def _release(cls, uid):
        lk = DBLock.get(uid)
        lk.delete()

    def __enter__(self):
        lk = self._acquire(self.uid, self.identity)
        if lk.identity != self.identity:
            while self.retries:
                time.sleep(self.wait)
                lk = self._acquire(self.uid, self.identity)
                self.retries -= 1
            else:
                if lk.identity != self.identity:
                    raise RuntimeError(
                        'Lock for {} is acquired by identity {}'.format(
                            lk.key, lk.identity))

    def __exit__(self, *err):
        self._release(self.uid)
