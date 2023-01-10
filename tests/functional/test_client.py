import logging
import os
import unittest
from unittest import mock

from pytest import fixture

import botocore
from tests import temporary_file, create_session

# logger = logging.getLogger()
# logger.setLevel(logging.DEBUG)

_GLOBAL_ENVVAR_ENDPOINT = "https://envvar-global.endpoint.aws/"
_PROFILE_GLOBAL_ENDPOINT = "https://global-profile.endpoint.aws/"
_PROFILE_S3_ENDPOINT = "https://s3-profile.endpoint.aws/"
_S3_ENVVAR_ENDPOINT = "https://envvar-s3.endpoint.aws/"
_CLIENT_CONSTRUCTOR_S3_ENDPOINT = "https://client-s3.endpoint.aws/"


@fixture
def mock_botocore_session():
    return botocore.session.get_session()


def mockenv(**envvars):
    return mock.patch.dict(os.environ, envvars, clear=True)


class TestCreateClients(unittest.TestCase):
    def setUp(self):
        self.session = botocore.session.get_session()

    def test_client_can_clone_with_service_events(self):
        # We should also be able to create a client object.
        client = self.session.create_client('s3', region_name='us-west-2')
        # We really just want to ensure create_client doesn't raise
        # an exception, but we'll double check that the client looks right.
        self.assertTrue(hasattr(client, 'list_buckets'))

    def test_client_raises_exception_invalid_region(self):
        with self.assertRaisesRegex(ValueError, ('invalid region name')):
            self.session.create_client(
                'cloudformation', region_name='invalid region name'
            )


def create_profile_string(endpoint_url=None, service_endpoints=None):
    profile_str = ('[profile test]\n'
                   'region=us-woohoo-2\n'
                   'aws_access_key_id=shared_creds_akid\n'
                   'aws_secret_access_key=shared_creds_sak\n')

    if endpoint_url:
        profile_str += f'endpoint_url={endpoint_url}\n'

    if service_endpoints:
        for key, val in service_endpoints.items():
            if key is None:
                profile_str += 
            else:
                profile_str += f"{key} = \n  endpoint_url = {val}"
    return profile_str

def create_env_dict(endpoint_url=None, service_endpoints=None):
    pass

def create_mock_endpoint_test(
    profile_endpoint_url=None, profile_service_endpoints=None,
    env_endpoint_url=None, env_service_endpoints=None):

    profile_string = create_profile_string(
        endpoint_url=profile_endpoint_url,
        service_endpoints=profile_service_endpoints)

    env_dict = create_env_dict(
        endpoint_url=env_endpoint_url,
        service_endpoints=env_service_endpoints)

    return profile_string, env_dict


class TestOtherClientStuff:

    def test_s3(self):
        """
        Set the S3-specific env variable and a config file global endpoint.

        The service specific env variable should take precedence over the
        config file global.
        """
        mock_botocore_session = botocore.session.get_session()
        with temporary_file('w') as f, \
            mock.patch.dict(
                os.environ,
                {"AWS_ENDPOINT_URL_S3": _S3_ENVVAR_ENDPOINT,
                 "AWS_CONFIG_FILE": f.name}, clear=True) as mockenv:
            profile_string = create_profile_string(
                endpoint_url=_PROFILE_GLOBAL_ENDPOINT)
            f.write(profile_string)
            f.flush()
            mock_botocore_session.set_config_variable(
                'profile', 'test_s3'
            )
            assert os.environ['AWS_ENDPOINT_URL_S3'] == _S3_ENVVAR_ENDPOINT

            s3_client = mock_botocore_session.create_client("s3")
            assert s3_client.meta.endpoint_url == _S3_ENVVAR_ENDPOINT

            kms_client = mock_botocore_session.create_client("kms")
            assert kms_client.meta.endpoint_url == _PROFILE_GLOBAL_ENDPOINT

    def test_s3_2(self, mock_botocore_session):
        """
        Set the S3-specific env variable and a config file global endpoint.

        The service specific env variable should take precedence over the
        config file global.
        """
        with temporary_file('w') as f, \
             mock.patch.dict(
                os.environ,
                {"AWS_ENDPOINT_URL_S3": _S3_ENVVAR_ENDPOINT,
                 "AWS_CONFIG_FILE": f.name}, clear=True) as mockenv:

            profile_string = create_profile_string(
                service_endpoints={"s3": _PROFILE_S3_ENDPOINT})
            f.write(profile_string)
            f.flush()

            mock_botocore_session.set_config_variable('profile', 'test_s3')

            assert os.environ['AWS_ENDPOINT_URL_S3'] == _S3_ENVVAR_ENDPOINT

            s3_client = mock_botocore_session.create_client("s3")
            assert s3_client.meta.endpoint_url == _S3_ENVVAR_ENDPOINT

            kms_client = mock_botocore_session.create_client("kms")
            assert kms_client.meta.endpoint_url != _PROFILE_GLOBAL_ENDPOINT
            assert kms_client.meta.endpoint_url != _S3_ENVVAR_ENDPOINT

    def test_s3_3(self):
        """
        Set the S3-specific env variable and a config file global endpoint.

        The service specific env variable should take precedence over the
        config file global.
        """
        mock_botocore_session = botocore.session.get_session()
        with temporary_file('w') as f, \
            mock.patch.dict(
                os.environ,
                {"AWS_ENDPOINT_URL_S3": _S3_ENVVAR_ENDPOINT,
                 "AWS_ENDPOINT_URL": _GLOBAL_ENVVAR_ENDPOINT,
                 "AWS_CONFIG_FILE": f.name}, clear=True) as mockenv:

            profile_string = create_profile_string()
            f.write(profile_string)
            f.flush()

            mock_botocore_session.set_config_variable(
                'profile', 'test_s3'
            )
            assert os.environ['AWS_ENDPOINT_URL_S3'] == _S3_ENVVAR_ENDPOINT

            s3_client = mock_botocore_session.create_client("s3")
            assert s3_client.meta.endpoint_url == _S3_ENVVAR_ENDPOINT

            kms_client = mock_botocore_session.create_client("kms")
            assert kms_client.meta.endpoint_url == _GLOBAL_ENVVAR_ENDPOINT

    def test_s3_4(self):
        """
        Set the global env variable and a config file service-specific S3 endpoint.

        The global env variable should take precedence over the 
        service-specific config file.

        """
        mock_botocore_session = botocore.session.get_session()
        with temporary_file('w') as f, \
            mock.patch.dict(
                os.environ,
                {"AWS_ENDPOINT_URL": _GLOBAL_ENVVAR_ENDPOINT,
                 "AWS_CONFIG_FILE": f.name}, clear=True) as mockenv:
            f.write(
                f'[profile test]\n'
                f'region=us-woohoo-2\n'
                f'aws_access_key_id=shared_creds_akid\n'
                f'aws_secret_access_key=shared_creds_sak\n'
                f's3 = \n'
                f'  endpoint_url={_PROFILE_S3_ENDPOINT}\n'

            )
            f.flush()
            mock_botocore_session.set_config_variable(
                'profile', 'test'
            )
            assert os.environ['AWS_ENDPOINT_URL'] == _GLOBAL_ENVVAR_ENDPOINT

            s3_client = mock_botocore_session.create_client("s3")
            assert s3_client.meta.endpoint_url == _GLOBAL_ENVVAR_ENDPOINT

            kms_client = mock_botocore_session.create_client("kms")
            assert kms_client.meta.endpoint_url == _GLOBAL_ENVVAR_ENDPOINT

    def test_s3_x(self):
        """
        Set the S3-specific env variable and a config file global endpoint.

        The service specific env variable should take precedence over the
        config file global.
        """
        mock_botocore_session = botocore.session.get_session()
        with temporary_file('w') as f, \
            mock.patch.dict(
                os.environ,
                {"AWS_ENDPOINT_URL_S3": _S3_ENVVAR_ENDPOINT,
                 "AWS_CONFIG_FILE": f.name}) as mockenv:
            f.write(
                f'[profile test_s3]\n'
                f'region=us-woohoo-2\n'
                f'aws_access_key_id=shared_creds_akid\n'
                f'aws_secret_access_key=shared_creds_sak\n'
                f's3 = \n'
                f'  endpoint_url={_PROFILE_S3_ENDPOINT}\n'
            )
            f.flush()
            mock_botocore_session.set_config_variable(
                'profile', 'test_s3'
            )
            assert os.environ['AWS_ENDPOINT_URL_S3'] == _S3_ENVVAR_ENDPOINT

            s3_client = mock_botocore_session.create_client(
                "s3", endpoint_url=_CLIENT_CONSTRUCTOR_S3_ENDPOINT)
            assert s3_client.meta.endpoint_url == \
                _CLIENT_CONSTRUCTOR_S3_ENDPOINT

            kms_client = mock_botocore_session.create_client("kms")
            assert kms_client.meta.endpoint_url != _PROFILE_GLOBAL_ENDPOINT
            assert kms_client.meta.endpoint_url != _S3_ENVVAR_ENDPOINT
