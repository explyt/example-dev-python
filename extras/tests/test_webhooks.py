import json
from unittest.mock import patch, MagicMock

import requests
from django.test import RequestFactory
from django_rq import get_queue
from jinja2 import TemplateError

from core.models import ObjectType
from dcim.models import Site
from extras.models import EventRule, Webhook
from extras.webhooks import send_webhook, register_webhook_callback
from extras.choices import EventRuleActionChoices
from utilities.testing import APITestCase
from utilities.proxy import resolve_proxies as real_resolve_proxies


class WebhookUnitTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        site_type = ObjectType.objects.get_for_model(Site)
        cls.dummy_url = 'http://localhost:9000/'
        cls.webhook = Webhook.objects.create(name='W', payload_url=cls.dummy_url, secret='sekrit')
        cls.webhook_no_secret = Webhook.objects.create(name='W2', payload_url=cls.dummy_url, secret='')
        webhook_type = ObjectType.objects.get(app_label='extras', model='webhook')
        cls.event_rule = EventRule.objects.create(
            name='ER',
            event_types=['object.created'],
            action_type=EventRuleActionChoices.WEBHOOK,
            action_object_type=webhook_type,
            action_object_id=cls.webhook.id,
            action_data={}
        )
        cls.object_type = ObjectType.objects.get_for_model(Site)

    def setUp(self):
        self.queue = get_queue('default')
        self.queue.empty()
        self.request = RequestFactory().get('/')
        self.request.id = None
        self.request.user = self.user

    def _base_kwargs(self, webhook_obj=None):
        event_rule = self.event_rule
        if webhook_obj:
            event_rule = EventRule.objects.get(name='ER')
            event_rule.action_object = webhook_obj
        return dict(
            event_rule=event_rule,
            object_type=self.object_type,
            event_type='object.created',
            data={'id': 1, 'name': 'Site 1'},
            timestamp='ts',
            username='testuser',
            request=self.request,
        )

    def test_render_headers_template_error_raises(self):
        kwargs = self._base_kwargs()
        webhook = self.webhook
        # Force render_headers to raise
        with patch.object(Webhook, 'render_headers', side_effect=TemplateError('boom')):
            with self.assertRaises(TemplateError):
                send_webhook(**kwargs)

    def test_render_body_template_error_raises(self):
        kwargs = self._base_kwargs()
        # render_headers OK, render_body raises
        with patch.object(Webhook, 'render_headers', return_value={}), \
             patch.object(Webhook, 'render_body', side_effect=TemplateError('boom')):
            with self.assertRaises(TemplateError):
                send_webhook(**kwargs)

    def test_requests_prepare_raises_request_exception(self):
        kwargs = self._base_kwargs()
        with patch.object(Webhook, 'render_headers', return_value={}), \
             patch.object(Webhook, 'render_body', return_value='{}'), \
             patch.object(Webhook, 'render_payload_url', return_value=self.dummy_url), \
             patch('requests.Request.prepare', side_effect=requests.exceptions.RequestException('bad')):
            with self.assertRaises(requests.exceptions.RequestException):
                send_webhook(**kwargs)

    def test_no_signature_when_secret_empty(self):
        kwargs = self._base_kwargs(webhook_obj=self.webhook_no_secret)
        # Prepare a fake prepared request to inspect headers
        prepared = MagicMock()
        prepared.body = b'{}'
        prepared.headers = {}

        # Patch to return our prepared request and a successful response
        req_mock = MagicMock()
        req_mock.prepare.return_value = prepared
        response = MagicMock(status_code=200, content=b'ok')

        with patch('requests.Request', return_value=req_mock), \
             patch('requests.Session') as SessionMock:
            session_inst = SessionMock.return_value.__enter__.return_value
            session_inst.send.return_value = response
            # call
            send_webhook(**kwargs)
            # ensure signature not set
            self.assertNotIn('X-Hook-Signature', prepared.headers)

    def test_non_2xx_response_raises_request_exception(self):
        kwargs = self._base_kwargs()
        prepared = MagicMock()
        prepared.body = b'{}'
        prepared.headers = {}
        req_mock = MagicMock()
        req_mock.prepare.return_value = prepared
        response = MagicMock(status_code=500, content=b'err')

        with patch('requests.Request', return_value=req_mock), \
             patch('requests.Session') as SessionMock:
            session_inst = SessionMock.return_value.__enter__.return_value
            session_inst.send.return_value = response
            with self.assertRaises(requests.exceptions.RequestException) as cm:
                send_webhook(**kwargs)
            self.assertIn('Status 500', str(cm.exception))
            self.assertIn("b'err'", str(cm.exception))

    def test_session_verify_and_ca_file_path_behavior(self):
        kwargs = self._base_kwargs()
        # Test ssl_verification True
        wh = self.webhook
        wh.ssl_verification = True
        wh.ca_file_path = ''
        wh.save()

        prepared = MagicMock(); prepared.body = b'{}'; prepared.headers = {}
        req_mock = MagicMock(); req_mock.prepare.return_value = prepared
        response = MagicMock(status_code=200, content=b'ok')

        with patch('requests.Request', return_value=req_mock), patch('requests.Session') as SessionMock:
            session_inst = SessionMock.return_value.__enter__.return_value
            session_inst.send.return_value = response
            send_webhook(**kwargs)
            self.assertTrue(session_inst.verify)

        # Test ca_file_path overrides verify
        wh.ca_file_path = '/tmp/ca.pem'
        wh.save()
        with patch('requests.Request', return_value=req_mock), patch('requests.Session') as SessionMock:
            session_inst = SessionMock.return_value.__enter__.return_value
            session_inst.send.return_value = response
            send_webhook(**kwargs)
            self.assertEqual(session_inst.verify, '/tmp/ca.pem')

    def test_resolve_proxies_used_in_session_send(self):
        kwargs = self._base_kwargs()
        prepared = MagicMock(); prepared.body = b'{}'; prepared.headers = {}
        req_mock = MagicMock(); req_mock.prepare.return_value = prepared
        response = MagicMock(status_code=200, content=b'ok')

        with patch('extras.webhooks.resolve_proxies', return_value={'http': 'http://proxy:8080'}) as rp, \
             patch('requests.Request', return_value=req_mock), patch('requests.Session') as SessionMock:
            session_inst = SessionMock.return_value.__enter__.return_value
            session_inst.send.return_value = response
            send_webhook(**kwargs)
            session_inst.send.assert_called()
            # check that resolve_proxies was called with url and client
            rp.assert_called()

    def test_webhook_callbacks_exceptions_are_swallowed_and_continue(self):
        kwargs = self._base_kwargs()
        # Prepare response
        prepared = MagicMock(); prepared.body = b'{}'; prepared.headers = {}
        req_mock = MagicMock(); req_mock.prepare.return_value = prepared
        response = MagicMock(status_code=200, content=b'ok')

        # Replace registry callbacks temporarily
        import netbox.registry as registry_module
        old = registry_module.registry.get('webhook_callbacks', []).copy()
        def bad_cb(*a, **k):
            raise Exception('boom')
        def good_cb(*a, **k):
            return {'ok': 1}
        registry_module.registry['webhook_callbacks'] = [bad_cb, good_cb]

        try:
            with patch('requests.Request', return_value=req_mock), patch('requests.Session') as SessionMock:
                session_inst = SessionMock.return_value.__enter__.return_value
                session_inst.send.return_value = response
                # Should not raise
                res = send_webhook(**kwargs)
                self.assertIn('webhook successfully processed', res)
        finally:
            registry_module.registry['webhook_callbacks'] = old

    def test_webhook_callbacks_non_dict_return_ignored(self):
        kwargs = self._base_kwargs()
        prepared = MagicMock(); prepared.body = b'{}'; prepared.headers = {}
        req_mock = MagicMock(); req_mock.prepare.return_value = prepared
        response = MagicMock(status_code=200, content=b'ok')

        import netbox.registry as registry_module
        old = registry_module.registry.get('webhook_callbacks', []).copy()
        registry_module.registry['webhook_callbacks'] = [lambda *a, **k: None, lambda *a, **k: 's', lambda *a, **k: {'x': 2}]

        try:
            with patch('requests.Request', return_value=req_mock), patch('requests.Session') as SessionMock:
                session_inst = SessionMock.return_value.__enter__.return_value
                session_inst.send.return_value = response
                res = send_webhook(**kwargs)
                self.assertIn('webhook successfully processed', res)
        finally:
            registry_module.registry['webhook_callbacks'] = old

    def test_register_webhook_callback_appends_to_registry(self):
        import netbox.registry as registry_module
        old = registry_module.registry.get('webhook_callbacks', []).copy()
        registry_module.registry['webhook_callbacks'] = []

        def dummy_cb(*a, **k):
            return {'a': 1}

        try:
            ret = register_webhook_callback(dummy_cb)
            self.assertIs(ret, dummy_cb)
            self.assertIn(dummy_cb, registry_module.registry['webhook_callbacks'])
        finally:
            registry_module.registry['webhook_callbacks'] = old
