# Standard Libraries
import logging
from datetime import date, datetime, timedelta

# Django Imports
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str

# Ghostwriter Libraries
from ghostwriter.api import utils
from ghostwriter.api.models import APIKey
from ghostwriter.factories import (
    ActivityTypeFactory,
    DomainFactory,
    DomainStatusFactory,
    ProjectAssignmentFactory,
    ProjectFactory,
    ReportFactory,
    ServerRoleFactory,
    ServerStatusFactory,
    StaticServerFactory,
    UserFactory,
)

logging.disable(logging.CRITICAL)

PASSWORD = "SuperNaturalReporting!"


# Tests related to the authentication webhook


class HasuraWebhookTests(TestCase):
    """Collection of tests for :view:`api:graphql_webhook`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.inactive_user = UserFactory(password=PASSWORD, is_active=False)
        cls.uri = reverse("api:graphql_webhook")
        cls.public_data = {
            "X-Hasura-Role": "public",
            "X-Hasura-User-Id": "-1",
            "X-Hasura-User-Name": "anonymous",
        }

        yesterday = timezone.now() - timedelta(days=1)
        cls.user_token_obj, cls.user_token = APIKey.objects.create_token(
            user=cls.user, name="Valid Token"
        )
        cls.inactive_token_obj, cls.inactive_token = APIKey.objects.create_token(
            user=cls.inactive_user, name="Inactive User Token"
        )
        cls.expired_token_obj, cls.expired_token = APIKey.objects.create_token(
            user=cls.inactive_user, name="Expired Token", expiry_date=yesterday
        )
        cls.revoked_token_obj, cls.revoked_token = APIKey.objects.create_token(
            user=cls.inactive_user, name="Revoked Token", revoked=True
        )

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def test_graphql_webhook_with_valid_jwt(self):
        _, token = utils.generate_jwt(self.user)
        data = {
            "X-Hasura-Role": f"{self.user.role}",
            "X-Hasura-User-Id": f"{self.user.id}",
            "X-Hasura-User-Name": f"{self.user.username}",
        }
        response = self.client.get(
            self.uri,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}", },
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(force_str(response.content), data)

    def test_graphql_webhook_with_valid_jwt_and_inactive_user(self):
        _, token = utils.generate_jwt(self.user)
        self.user.is_active = False
        self.user.save()
        response = self.client.get(
            self.uri,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}", },
        )
        self.assertEqual(response.status_code, 401)
        self.assertJSONEqual(force_str(response.content), self.public_data)
        self.user.is_active = True
        self.user.save()

    def test_graphql_webhook_with_invalid_jwt(self):
        token = "GARBAGE!"
        response = self.client.get(
            self.uri,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}", },
        )
        self.assertEqual(response.status_code, 401)
        self.assertJSONEqual(force_str(response.content), self.public_data)

    def test_graphql_webhook_with_valid_tracked_token(self):
        data = {
            "X-Hasura-Role": f"{self.user.role}",
            "X-Hasura-User-Id": f"{self.user.id}",
            "X-Hasura-User-Name": f"{self.user.username}",
        }
        response = self.client.get(
            self.uri,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.user_token}", },
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(force_str(response.content), data)

    def test_graphql_webhook_with_valid_tracked_token_and_inactive_user(self):
        response = self.client.get(
            self.uri,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.inactive_token}", },
        )
        self.assertEqual(response.status_code, 401)
        self.assertJSONEqual(force_str(response.content), self.public_data)

    def test_graphql_webhook_with_expired_tracked_token(self):
        response = self.client.get(
            self.uri,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.expired_token}", },
        )
        self.assertEqual(response.status_code, 401)
        self.assertJSONEqual(force_str(response.content), self.public_data)

    def test_graphql_webhook_with_revoked_tracked_token(self):
        response = self.client.get(
            self.uri,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {self.revoked_token}", },
        )
        self.assertEqual(response.status_code, 401)
        self.assertJSONEqual(force_str(response.content), self.public_data)


# Tests related to Hasura Actions


class HasuraLoginTests(TestCase):
    """Collection of tests for :view:`api:graphql_login`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.uri = reverse("api:graphql_login")

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def test_graphql_login(self):
        data = {
            "input": {"username": f"{self.user.username}", "password": f"{PASSWORD}"}
        }
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", },
        )
        self.assertEqual(response.status_code, 200)
        # Test bypasses Hasura so the ``["data"]["login"]`` keys are not present
        self.assertTrue(response.json()["token"])

    def test_graphql_login_with_invalid_credentials(self):
        data = {
            "input": {"username": f"{self.user.username}", "password": "Not the Password"}
        }
        result = {
            "message": "Invalid credentials",
            "extensions": {"code": "InvalidCredentials", },
        }
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", },
        )
        self.assertEqual(response.status_code, 401)
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_login_requires_secret(self):
        data = {
            "input": {"username": f"{self.user.username}", "password": f"{PASSWORD}"}
        }
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_graphql_login_rejects_bad_request(self):
        data = {
            "bad_input": {"username": f"{self.user.username}", "password": f"{PASSWORD}"}
        }
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", },
        )
        self.assertEqual(response.status_code, 400)

    def test_graphql_login_without_secret(self):
        data = {
            "input": {"username": f"{self.user.username}", "password": f"{PASSWORD}"}
        }
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        result = {
            "message": "Unauthorized access method",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_login_with_invalid_secret(self):
        data = {
            "input": {"username": f"{self.user.username}", "password": f"{PASSWORD}"}
        }
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "wrong", },
        )
        self.assertEqual(response.status_code, 403)

        result = {
            "message": "Unauthorized access method",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)


class HasuraWhoamiTests(TestCase):
    """Collection of tests for :view:`api:GraphqlWhoami`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.uri = reverse("api:graphql_whoami")

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def test_graphql_whoami(self):
        _, token = utils.generate_jwt(self.user)
        response = self.client.post(
            self.uri,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        # Test bypasses Hasura so the ``["data"]["whoami"]`` keys are not present
        self.assertEqual(response.json()["username"], self.user.username)

    def test_graphql_whoami_with_tracked_token(self):
        user_token_obj, user_token = APIKey.objects.create_token(
            user=self.user, name="Valid Token"
        )
        response = self.client.post(
            self.uri,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {user_token}"},
        )
        self.assertEqual(response.status_code, 200)
        # Test bypasses Hasura so the ``["data"]["whoami"]`` keys are not present
        self.assertEqual(response.json()["username"], self.user.username)

    def test_graphql_whoami_rejects_missing_jwt(self):
        response = self.client.post(
            self.uri,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", },
        )
        self.assertEqual(response.status_code, 400)

    def test_graphql_whoami_requires_valid_jwt(self):
        token = "GARBAGE!"
        response = self.client.post(
            self.uri,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_graphql_whoami_without_secret(self):
        response = self.client.post(
            self.uri,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        result = {
            "message": "Unauthorized access method",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)


class HasuraGenerateReportTests(TestCase):
    """Collection of tests for :view:`api:GraphqlGenerateReport`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.assignment = ProjectAssignmentFactory(operator=cls.user)
        cls.report = ReportFactory(project=cls.assignment.project)
        cls.other_report = ReportFactory()
        cls.uri = reverse("api:graphql_generate_report")

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def test_graphql_generate_report(self):
        _, token = utils.generate_jwt(self.user)
        data = {"input": {"id": self.report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)

    def test_graphql_generate_report_with_tracked_token(self):
        _, user_token = APIKey.objects.create_token(
            user=self.user, name="Valid Token"
        )
        data = {"input": {"id": self.report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {user_token}"},
        )
        self.assertEqual(response.status_code, 200)

    def test_graphql_generate_report_with_invalid_report(self):
        _, token = utils.generate_jwt(self.user)
        data = {"input": {"id": 999}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

        result = {
            "message": "Unauthorized access",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_generate_report_without_access(self):
        _, token = utils.generate_jwt(self.user)
        data = {"input": {"id": self.other_report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

        result = {
            "message": "Unauthorized access",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_generate_report_rejects_missing_jwt(self):
        data = {"input": {"id": self.report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", },
        )
        self.assertEqual(response.status_code, 400)

    def test_graphql_generate_report_requires_valid_jwt(self):
        token = "GARBAGE!"
        data = {"input": {"id": self.report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_graphql_generate_report_without_secret(self):
        data = {"input": {"id": self.report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        result = {
            "message": "Unauthorized access method",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_generate_report_with_invalid_payload(self):
        _, token = utils.generate_jwt(self.user)
        data = {"wrong": {"id": self.report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Invalid request body",
            "extensions": {"code": "InvalidRequestBody", },
        }
        self.assertJSONEqual(force_str(response.content), result)

        data = {"input": {"wrong": self.report.pk}}
        response = self.client.post(
            self.uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Invalid request body",
            "extensions": {"code": "InvalidRequestBody", },
        }
        self.assertJSONEqual(force_str(response.content), result)


class HasuraCheckoutTests(TestCase):
    """
    Collection of tests for the :view:``api:CheckoutView`` and the related
    :view:`api:GraphqlCheckoutDomain` and :view:`api:GraphqlCheckoutServer`.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.activity = ActivityTypeFactory()
        cls.project = ProjectFactory()
        cls.other_project = ProjectFactory()
        cls.assignment = ProjectAssignmentFactory(operator=cls.user, project=cls.project)

        cls.domain_unavailable = DomainStatusFactory(domain_status="Unavailable")
        cls.domain = DomainFactory()
        cls.unavailable_domain = DomainFactory(domain_status=cls.domain_unavailable)
        cls.expired_domain = DomainFactory(expiration=timezone.now() - timedelta(days=1))

        cls.server_unavailable = ServerStatusFactory(server_status="Unavailable")
        cls.server = StaticServerFactory()
        cls.unavailable_server = StaticServerFactory(server_status=cls.server_unavailable)
        cls.server_role = ServerRoleFactory()

        cls.domain_uri = reverse("api:graphql_checkout_domain")
        cls.server_uri = reverse("api:graphql_checkout_server")

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def generate_domain_data(
        self, project, domain, activity,
        start_date=date.today() - timedelta(days=1),
        end_date=date.today() + timedelta(days=1),
        note=None
    ):
        return {
            "input": {
                "projectId": project,
                "domainId": domain,
                "activityTypeId": activity,
                "startDate": start_date,
                "endDate": end_date,
                "note": note,
            }
        }

    def generate_server_data(
        self, project, server, activity, server_role,
        start_date=date.today() - timedelta(days=1),
        end_date=date.today() + timedelta(days=1),
        note=None
    ):
        return {
            "input": {
                "projectId": project,
                "serverId": server,
                "activityTypeId": activity,
                "serverRoleId": server_role,
                "startDate": start_date,
                "endDate": end_date,
                "note": note,
            }
        }

    def test_graphql_checkout_domain(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(self.project.pk, self.domain.pk, self.activity.pk, note="Test note")
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(force_str(response.content), {"result": "success", })
        self.domain.refresh_from_db()
        self.assertEqual(self.domain.domain_status, self.domain_unavailable)

    def test_graphql_checkout_server(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_server_data(self.project.pk, self.domain.pk, self.activity.pk, self.server_role.pk, note="Test note")
        response = self.client.post(
            self.server_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(force_str(response.content), {"result": "success", })
        self.server.refresh_from_db()
        self.assertEqual(self.server.server_status, self.server_unavailable)

    def test_graphql_checkout_object_with_invalid_dates(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(
            self.project.pk,
            self.domain.pk,
            self.activity.pk,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() - timedelta(days=1),
        )
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "End date is before start date",
            "extensions": {"code": "InvalidDates", },
        }
        self.assertJSONEqual(force_str(response.content), result)

        data = self.generate_domain_data(
            self.project.pk,
            self.domain.pk,
            self.activity.pk,
            start_date="2022-0325",
            end_date=date.today() - timedelta(days=1),
        )
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Invalid date values (must be YYYY-MM-DD)",
            "extensions": {"code": "InvalidDates", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_invalid_object(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(self.project.pk, 999, self.activity.pk)
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Domain does not exist",
            "extensions": {"code": "DomainDoesNotExist", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_invalid_activity(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(self.project.pk, self.domain.pk, 999)
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Activity Type does not exist",
            "extensions": {"code": "ActivityTypeDoesNotExist", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_invalid_project(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(999, self.domain.pk, self.activity.pk)
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

        result = {
            "message": "Unauthorized access",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_unavailable_domain(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(self.project.pk, self.unavailable_domain.pk, self.activity.pk)
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Domain is unavailable",
            "extensions": {"code": "DomainUnavailable", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_unavailable_server(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_server_data(self.project.pk, self.unavailable_server.pk, self.activity.pk, self.server_role.pk)
        response = self.client.post(
            self.server_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Server is unavailable",
            "extensions": {"code": "ServerUnavailable", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_expired_domain(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(self.project.pk, self.expired_domain.pk, self.activity.pk)
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Domain is expired",
            "extensions": {"code": "DomainExpired", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_without_project_access(self):
        _, token = utils.generate_jwt(self.user)
        data = self.generate_domain_data(self.other_project.pk, self.domain.pk, self.activity.pk)
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 401)

        result = {
            "message": "Unauthorized access",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)

    def test_graphql_checkout_with_invalid_payload(self):
        _, token = utils.generate_jwt(self.user)
        data = {"wrong": {"id": 1}}
        response = self.client.post(
            self.domain_uri,
            data=data,
            content_type="application/json",
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", "HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 400)

        result = {
            "message": "Invalid request body",
            "extensions": {"code": "InvalidRequestBody", },
        }
        self.assertJSONEqual(force_str(response.content), result)


# Tests related to Hasura Event Triggers


class HasuraDomainUpdateEventTests(TestCase):
    """Collection of tests for :view:`api:graphql_domain_update_event`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.uri = reverse("api:graphql_domain_update_event")
        cls.domain = DomainFactory(name="chrismaddalena.com")
        cls.sample_data = {
            "event": {
                "data": {
                    "new": {
                        "expired": False,
                        "registrar": "Hover",
                        "note": "<p>The personal website and blog of Christopher Maddalena</p>",
                        "last_health_check": "",
                        "auto_renew": True,
                        "expiration": "2023-03-25",
                        "reset_dns": False,
                        "vt_permalink": "",
                        "burned_explanation": "",
                        "creation": "2010-03-25",
                        "domain_status_id": cls.domain.domain_status.id,
                        "last_used_by_id": "",
                        "name": "Chrismaddalena.com",
                        "categorization": "",
                        "health_status_id": cls.domain.health_status.id,
                        "id": cls.domain.id,
                        "whois_status_id": 1,
                        "dns": {}
                    },
                    "old": {},
                },
            }
        }

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def test_graphql_domain_update_event(self):
        payload, token = utils.generate_jwt(self.user)
        response = self.client.post(
            self.uri,
            content_type="application/json",
            data=self.sample_data,
            **{"HTTP_HASURA_ACTION_SECRET": "changeme", },
        )
        self.assertEqual(response.status_code, 200)

    def test_graphql_domain_update_event_without_secret(self):
        response = self.client.post(
            self.uri,
            data=self.sample_data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        result = {
            "message": "Unauthorized access method",
            "extensions": {"code": "Unauthorized", },
        }
        self.assertJSONEqual(force_str(response.content), result)


# Tests related to CBVs for :model:`api:APIKey`


class ApiKeyRevokeTests(TestCase):
    """Collection of tests for :view:`api:ApiKeyRevoke`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.other_user = UserFactory(password=PASSWORD)
        cls.token_obj, cls.token = APIKey.objects.create_token(
            user=cls.user, name="User's Token"
        )
        cls.other_token_obj, cls.other_token = APIKey.objects.create_token(
            user=cls.other_user, name="Other User's Token"
        )
        cls.uri = reverse("api:ajax_revoke_token", kwargs={"pk": cls.token_obj.pk})
        cls.other_uri = reverse("api:ajax_revoke_token", kwargs={"pk": cls.other_token_obj.pk})

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def test_view_uri_exists_at_desired_location(self):
        data = {"result": "success", "message": "Token successfully revoked!"}
        response = self.client_auth.post(self.uri)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(force_str(response.content), data)

        self.token_obj.refresh_from_db()
        self.assertEqual(self.token_obj.revoked, True)

    def test_view_requires_login(self):
        response = self.client.get(self.uri)
        self.assertEqual(response.status_code, 302)

    def test_revoking_another_users_token(self):
        response = self.client.post(self.other_uri)
        self.assertEqual(response.status_code, 302)


class ApiKeyCreateTests(TestCase):
    """Collection of tests for :view:`api:ApiKeyCreate`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(password=PASSWORD)
        cls.uri = reverse("api:ajax_create_token")
        cls.redirect_uri = reverse("users:user_detail", kwargs={"username": cls.user.username})

    def setUp(self):
        self.client = Client()
        self.client_auth = Client()
        self.client_auth.login(username=self.user.username, password=PASSWORD)
        self.assertTrue(
            self.client_auth.login(username=self.user.username, password=PASSWORD)
        )

    def test_view_uri_exists_at_desired_location(self):
        response = self.client_auth.get(self.uri)
        self.assertEqual(response.status_code, 200)

    def test_view_requires_login(self):
        response = self.client.get(self.uri)
        self.assertEqual(response.status_code, 302)

    def test_view_uses_correct_template(self):
        response = self.client_auth.get(self.uri)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "token_form.html")

    def test_custom_context_exists(self):
        response = self.client_auth.get(self.uri)
        self.assertIn("cancel_link", response.context)
        self.assertEqual(response.context["cancel_link"], self.redirect_uri)

    def test_post_data(self):
        response = self.client_auth.post(self.uri, data={"name": "CreateView Test", "expiry_date": datetime.now()})
        self.assertRedirects(response, self.redirect_uri)
        obj = APIKey.objects.get(name="CreateView Test")
        self.assertEqual(obj.user, self.user)
