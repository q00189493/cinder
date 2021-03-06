# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
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

from oslo.config import cfg
import webob

from cinder.api import extensions
from cinder.api.v1 import volume_metadata
from cinder.api.v1 import volumes
import cinder.db
from cinder import exception
from cinder.openstack.common import jsonutils
from cinder import test
from cinder.tests.api import fakes
from cinder.tests.api.v1 import stubs


CONF = cfg.CONF


def return_create_volume_metadata_max(context, volume_id, metadata, delete):
    return stub_max_volume_metadata()


def return_create_volume_metadata(context, volume_id, metadata, delete):
    return stub_volume_metadata()


def return_volume_metadata(context, volume_id):
    if not isinstance(volume_id, str) or not len(volume_id) == 36:
        msg = 'id %s must be a uuid in return volume metadata' % volume_id
        raise Exception(msg)
    return stub_volume_metadata()


def return_empty_volume_metadata(context, volume_id):
    return {}


def delete_volume_metadata(context, volume_id, key):
    pass


def stub_volume_metadata():
    metadata = {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }
    return metadata


def stub_max_volume_metadata():
    metadata = {"metadata": {}}
    for num in range(CONF.quota_metadata_items):
        metadata['metadata']['key%i' % num] = "blah"
    return metadata


def return_volume(context, volume_id):
    return {'id': '0cc3346e-9fef-4445-abe6-5d2b2690ec64',
            'name': 'fake',
            'metadata': {}}


def return_volume_nonexistent(context, volume_id):
    raise exception.VolumeNotFound('bogus test message')


def fake_update_volume_metadata(self, context, volume, diff):
    pass


class volumeMetaDataTest(test.TestCase):

    def setUp(self):
        super(volumeMetaDataTest, self).setUp()
        self.volume_api = cinder.volume.api.API()
        fakes.stub_out_key_pair_funcs(self.stubs)
        self.stubs.Set(cinder.db, 'volume_get', return_volume)
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_volume_metadata)
        self.stubs.Set(cinder.db, 'service_get_all_by_topic',
                       stubs.stub_service_get_all_by_topic)

        self.stubs.Set(self.volume_api, 'update_volume_metadata',
                       fake_update_volume_metadata)

        self.ext_mgr = extensions.ExtensionManager()
        self.ext_mgr.extensions = {}
        self.volume_controller = volumes.VolumeController(self.ext_mgr)
        self.controller = volume_metadata.Controller()
        self.id = str(uuid.uuid4())
        self.url = '/v1/fake/volumes/%s/metadata' % self.id

        vol = {"size": 100,
               "display_name": "Volume Test Name",
               "display_description": "Volume Test Desc",
               "availability_zone": "zone1:host1",
               "metadata": {}}
        body = {"volume": vol}
        req = fakes.HTTPRequest.blank('/v1/volumes')
        self.volume_controller.create(req, body)

    def test_index(self):
        req = fakes.HTTPRequest.blank(self.url)
        res_dict = self.controller.index(req, self.id)

        expected = {
            'metadata': {
                'key1': 'value1',
                'key2': 'value2',
                'key3': 'value3',
            },
        }
        self.assertEqual(expected, res_dict)

    def test_index_nonexistent_volume(self):
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_volume_nonexistent)
        req = fakes.HTTPRequest.blank(self.url)
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.index, req, self.url)

    def test_index_no_data(self):
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_empty_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url)
        res_dict = self.controller.index(req, self.id)
        expected = {'metadata': {}}
        self.assertEqual(expected, res_dict)

    def test_show(self):
        req = fakes.HTTPRequest.blank(self.url + '/key2')
        res_dict = self.controller.show(req, self.id, 'key2')
        expected = {'meta': {'key2': 'value2'}}
        self.assertEqual(expected, res_dict)

    def test_show_nonexistent_volume(self):
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_volume_nonexistent)
        req = fakes.HTTPRequest.blank(self.url + '/key2')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.show, req, self.id, 'key2')

    def test_show_meta_not_found(self):
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_empty_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key6')
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.show, req, self.id, 'key6')

    def test_delete(self):
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_volume_metadata)
        self.stubs.Set(cinder.db, 'volume_metadata_delete',
                       delete_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key2')
        req.method = 'DELETE'
        res = self.controller.delete(req, self.id, 'key2')

        self.assertEqual(200, res.status_int)

    def test_delete_nonexistent_volume(self):
        self.stubs.Set(cinder.db, 'volume_get',
                       return_volume_nonexistent)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'DELETE'
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.delete, req, self.id, 'key1')

    def test_delete_meta_not_found(self):
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_empty_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key6')
        req.method = 'DELETE'
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.delete, req, self.id, 'key6')

    def test_create(self):
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_empty_volume_metadata)
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)

        req = fakes.HTTPRequest.blank('/v1/volume_metadata')
        req.method = 'POST'
        req.content_type = "application/json"
        body = {"metadata": {"key9": "value9"}}
        req.body = jsonutils.dumps(body)
        res_dict = self.controller.create(req, self.id, body)
        self.assertEqual(body, res_dict)

    def test_create_empty_body(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url)
        req.method = 'POST'
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.create, req, self.id, None)

    def test_create_item_empty_key(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        body = {"meta": {"": "value1"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.create, req, self.id, body)

    def test_create_item_key_too_long(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        body = {"meta": {("a" * 260): "value1"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.create,
                          req, self.id, body)

    def test_create_nonexistent_volume(self):
        self.stubs.Set(cinder.db, 'volume_get',
                       return_volume_nonexistent)
        self.stubs.Set(cinder.db, 'volume_metadata_get',
                       return_volume_metadata)
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)

        req = fakes.HTTPRequest.blank('/v1/volume_metadata')
        req.method = 'POST'
        req.content_type = "application/json"
        body = {"metadata": {"key9": "value9"}}
        req.body = jsonutils.dumps(body)
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.create, req, self.id, body)

    def test_update_all(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url)
        req.method = 'PUT'
        req.content_type = "application/json"
        expected = {
            'metadata': {
                'key10': 'value10',
                'key99': 'value99',
            },
        }
        req.body = jsonutils.dumps(expected)
        res_dict = self.controller.update_all(req, self.id, expected)

        self.assertEqual(expected, res_dict)

    def test_update_all_empty_container(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url)
        req.method = 'PUT'
        req.content_type = "application/json"
        expected = {'metadata': {}}
        req.body = jsonutils.dumps(expected)
        res_dict = self.controller.update_all(req, self.id, expected)

        self.assertEqual(expected, res_dict)

    def test_update_all_malformed_container(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url)
        req.method = 'PUT'
        req.content_type = "application/json"
        expected = {'meta': {}}
        req.body = jsonutils.dumps(expected)

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update_all, req, self.id, expected)

    def test_update_all_malformed_data(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url)
        req.method = 'PUT'
        req.content_type = "application/json"
        expected = {'metadata': ['asdf']}
        req.body = jsonutils.dumps(expected)

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update_all, req, self.id, expected)

    def test_update_all_nonexistent_volume(self):
        self.stubs.Set(cinder.db, 'volume_get', return_volume_nonexistent)
        req = fakes.HTTPRequest.blank(self.url)
        req.method = 'PUT'
        req.content_type = "application/json"
        body = {'metadata': {'key10': 'value10'}}
        req.body = jsonutils.dumps(body)

        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.update_all, req, '100', body)

    def test_update_item(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        body = {"meta": {"key1": "value1"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"
        res_dict = self.controller.update(req, self.id, 'key1', body)
        expected = {'meta': {'key1': 'value1'}}
        self.assertEqual(expected, res_dict)

    def test_update_item_nonexistent_volume(self):
        self.stubs.Set(cinder.db, 'volume_get',
                       return_volume_nonexistent)
        req = fakes.HTTPRequest.blank('/v1.1/fake/volumes/asdf/metadata/key1')
        req.method = 'PUT'
        body = {"meta": {"key1": "value1"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.update, req, self.id, 'key1', body)

    def test_update_item_empty_body(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update, req, self.id, 'key1', None)

    def test_update_item_empty_key(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        body = {"meta": {"": "value1"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update, req, self.id, '', body)

    def test_update_item_key_too_long(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        body = {"meta": {("a" * 260): "value1"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          self.controller.update,
                          req, self.id, ("a" * 260), body)

    def test_update_item_value_too_long(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        body = {"meta": {"key1": ("a" * 260)}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          self.controller.update,
                          req, self.id, "key1", body)

    def test_update_item_too_many_keys(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/key1')
        req.method = 'PUT'
        body = {"meta": {"key1": "value1", "key2": "value2"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update, req, self.id, 'key1', body)

    def test_update_item_body_uri_mismatch(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url + '/bad')
        req.method = 'PUT'
        body = {"meta": {"key1": "value1"}}
        req.body = jsonutils.dumps(body)
        req.headers["content-type"] = "application/json"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update, req, self.id, 'bad', body)

    def test_invalid_metadata_items_on_create(self):
        self.stubs.Set(cinder.db, 'volume_metadata_update',
                       return_create_volume_metadata)
        req = fakes.HTTPRequest.blank(self.url)
        req.method = 'POST'
        req.headers["content-type"] = "application/json"

        #test for long key
        data = {"metadata": {"a" * 260: "value1"}}
        req.body = jsonutils.dumps(data)
        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          self.controller.create, req, self.id, data)

        #test for long value
        data = {"metadata": {"key": "v" * 260}}
        req.body = jsonutils.dumps(data)
        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          self.controller.create, req, self.id, data)

        #test for empty key.
        data = {"metadata": {"": "value1"}}
        req.body = jsonutils.dumps(data)
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.create, req, self.id, data)
