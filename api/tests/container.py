"""
Unit tests for the Deis api app.

Run the tests with "./manage.py test api"
"""

from __future__ import unicode_literals

import json

from django.test import TestCase

from deis import settings


def get_allocations(container_dict):
    counts = {}
    for container in container_dict.values():
        name, id = container.split(':')
        if name in counts:
            counts[name] += 1
        else:
            counts[name] = 1
    return sorted(counts.values())


class ContainerTest(TestCase):

    """Tests creation of containers on nodes"""

    fixtures = ['tests.json']

    def setUp(self):
        self.assertTrue(
            self.client.login(username='autotest', password='password'))
        url = '/api/providers'
        creds = {'access_key': getattr(settings, 'EC2_ACCESS_KEY', 'x' * 32),
                 'secret_key': getattr(settings, 'EC2_SECRET_KEY', 'x' * 64)}
        body = {'id': 'autotest', 'type': 'mock', 'creds': json.dumps(creds)}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        url = '/api/flavors'
        body = {'id': 'autotest', 'provider': 'autotest',
                'params': json.dumps({'region': 'us-west-2', 'instance_size': 'm1.medium'})}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_container_scale(self):
        url = '/api/formations'
        body = {'id': 'autotest'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        formation_id = response.data['id']
        url = "/api/formations/{formation_id}/layers".format(**locals())
        body = {'id': 'runtime', 'flavor': 'autotest', 'run_list': 'recipe[deis::runtime]'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        # scale runtime layer up
        url = "/api/formations/{formation_id}/scale/layers".format(**locals())
        body = {'runtime': 4}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        url = "/api/formations/{formation_id}/nodes".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 4)
        url = "/api/formations/{formation_id}".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # should start with zero
        url = "/api/formations/{formation_id}/containers".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)
        # scale up
        url = "/api/formations/{formation_id}/scale/containers".format(**locals())
        body = {'web': 4, 'worker': 2}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        url = "/api/formations/{formation_id}/containers".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 6)
        url = "/api/formations/{formation_id}".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['containers'], json.dumps(body))
        # scale down
        url = "/api/formations/{formation_id}/scale/containers".format(**locals())
        body = {'web': 2, 'worker': 1}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        url = "/api/formations/{formation_id}/containers".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 3)
        url = "/api/formations/{formation_id}".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['containers'], json.dumps(body))
        # scale down to 0
        url = "/api/formations/{formation_id}/scale/containers".format(**locals())
        body = {'web': 0, 'worker': 0}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        url = "/api/formations/{formation_id}/containers".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)
        url = "/api/formations/{formation_id}".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['containers'], json.dumps(body))

    def test_container_scale_allocation(self):
        url = '/api/formations'
        body = {'id': 'autotest'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        formation_id = response.data['id']
        url = "/api/formations/{formation_id}/layers".format(**locals())
        body = {'id': 'runtime', 'flavor': 'autotest', 'run_list': 'recipe[deis::runtime]'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        # With 4 nodes and 13 web containers
        url = "/api/formations/{formation_id}/scale/layers".format(**locals())
        body = {'runtime': 4}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        url = "/api/formations/{formation_id}/scale/containers".format(**locals())
        body = {'web': 13}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # test that one node has 4 and 3 nodes have 3 containers
        self.assertEqual(get_allocations(response.data['containers']['web']),
                         [3, 3, 3, 4])
        # With 1 node
        url = "/api/formations/{formation_id}/scale/layers".format(**locals())
        body = {'runtime': 1}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # test that the node has all 13 containers
        self.assertEqual(get_allocations(response.data['containers']['web']),
                         [13])
        # With 2 nodes
        url = "/api/formations/{formation_id}/scale/layers".format(**locals())
        body = {'runtime': 2}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # test that one has 6 and the other has 7 containers
        self.assertEqual(get_allocations(response.data['containers']['web']),
                         [6, 7])
        # With 8 containers
        url = "/api/formations/{formation_id}/scale/containers".format(**locals())
        body = {'web': 8}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # test that both have 4 containers
        self.assertEqual(get_allocations(response.data['containers']['web']),
                         [4, 4])
        # With 0 nodes
        url = "/api/formations/{formation_id}/scale/layers".format(**locals())
        body = {'runtime': 0}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # test that there are no containers
        self.assertNotIn('web', response.data['containers'])
        # With 5 containers
        url = "/api/formations/{formation_id}/scale/containers".format(**locals())
        body = {'web': 5}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        # test that we get an error message about runtime nodes
        self.assertEqual(response.status_code, 400)
        self.assertIn('Must scale runtime nodes', response.data)
        # With 1 node
        url = "/api/formations/{formation_id}/scale/layers".format(**locals())
        body = {'runtime': 1}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # test that it gets all 8 containers
        self.assertEqual(get_allocations(response.data['containers']['web']),
                         [8])

    def test_container_balance(self):
        url = '/api/formations'
        body = {'id': 'autotest'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        formation_id = response.data['id']
        url = '/api/formations/{formation_id}/layers'.format(**locals())
        body = {'id': 'runtime', 'flavor': 'autotest', 'run_list': 'recipe[deis::runtime]'}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        # scale layer
        url = '/api/formations/{formation_id}/scale/layers'.format(**locals())
        body = {'runtime': 2}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # should start with zero
        url = "/api/formations/{formation_id}/containers".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)
        # scale up
        url = '/api/formations/{formation_id}/scale/containers'.format(**locals())
        body = {'web': 8, 'worker': 2}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # scale layer up
        url = '/api/formations/{formation_id}/scale/layers'.format(**locals())
        body = {'runtime': 4}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # calculate the formation
        url = "/api/formations/{formation_id}/calculate".format(**locals())
        response = self.client.post(url)
        containers = response.data['containers']
        # check balance of web types
        by_backend = {}
        for c in containers['web'].values():
            backend, port = c.split(':')
            by_backend.setdefault(backend, []).append(port)
        b_min = min([len(by_backend[b]) for b in by_backend.keys()])
        b_max = max([len(by_backend[b]) for b in by_backend.keys()])
        self.assertLess(b_max - b_min, 2)
        # check balance of worker types
        by_backend = {}
        for c in containers['worker'].values():
            backend, port = c.split(':')
            by_backend.setdefault(backend, []).append(port)
        b_min = min([len(by_backend[b]) for b in by_backend.keys()])
        b_max = max([len(by_backend[b]) for b in by_backend.keys()])
        self.assertLess(b_max - b_min, 2)
        # scale up more
        url = '/api/formations/{formation_id}/scale/containers'.format(**locals())
        body = {'web': 6, 'worker': 4}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # calculate the formation
        url = "/api/formations/{formation_id}/calculate".format(**locals())
        response = self.client.post(url)
        containers = response.data['containers']
        # check balance of web types
        by_backend = {}
        for c in containers['web'].values():
            backend, port = c.split(':')
            by_backend.setdefault(backend, []).append(port)
        b_min = min([len(by_backend[b]) for b in by_backend.keys()])
        b_max = max([len(by_backend[b]) for b in by_backend.keys()])
        self.assertLess(b_max - b_min, 2)
        # check balance of worker types
        by_backend = {}
        for c in containers['worker'].values():
            backend, port = c.split(':')
            by_backend.setdefault(backend, []).append(port)
        b_min = min([len(by_backend[b]) for b in by_backend.keys()])
        b_max = max([len(by_backend[b]) for b in by_backend.keys()])
        self.assertLess(b_max - b_min, 2)
        # scale down
        url = '/api/formations/{formation_id}/scale/containers'.format(**locals())
        body = {'web': 2, 'worker': 2}
        response = self.client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        url = "/api/formations/{formation_id}/containers".format(**locals())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 4)
        # calculate the formation
        url = "/api/formations/{formation_id}/calculate".format(**locals())
        response = self.client.post(url)
        containers = response.data['containers']
        # check balance of web types
        by_backend = {}
        for c in containers['web'].values():
            backend, port = c.split(':')
            by_backend.setdefault(backend, []).append(port)
        b_min = min([len(by_backend[b]) for b in by_backend.keys()])
        b_max = max([len(by_backend[b]) for b in by_backend.keys()])
        self.assertLess(b_max - b_min, 2)
        # check balance of worker types
        by_backend = {}
        for c in containers['worker'].values():
            backend, port = c.split(':')
            by_backend.setdefault(backend, []).append(port)
        b_min = min([len(by_backend[b]) for b in by_backend.keys()])
        b_max = max([len(by_backend[b]) for b in by_backend.keys()])
        self.assertLess(b_max - b_min, 2)
