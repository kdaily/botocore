# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
import pytest

import botocore.session as session
from botocore.args import ConfiguredEndpointProviderChain
from botocore.model import ServiceModel
from tests import unittest


def _known_service_names_and_ids():
    my_session = session.get_session()
    loader = my_session.get_component('data_loader')
    available_services = loader.list_available_services('service-2')

    result = set()
    for service_name in available_services:
        model = my_session.get_service_model(service_name)
        result.add((model.service_name, model.service_id))
    return result


class TestCustomEndpointProviderChain(unittest.TestCase):
    def assert_chain_does_provide(
        self,
        service,
        instance_map,
        environ_map,
        full_config_map,
        scoped_config_map,
        expected_value,
    ):
        mocked_service_model = unittest.mock.Mock(spec=ServiceModel)
        mocked_service_model.service_id = service
        mocked_service_model.service_name = service

        chain = ConfiguredEndpointProviderChain(
            scoped_config=scoped_config_map,
            full_config=full_config_map,
            service_model=mocked_service_model,
            environ=environ_map,
        )
        value = chain.provide()
        self.assertEqual(value, expected_value)

    def test_chain_builder_can_provide_env_var(self):
        self.assert_chain_does_provide(
            service="batch",
            instance_map={},
            environ_map={'AWS_ENDPOINT_URL': 'from-env'},
            full_config_map={},
            scoped_config_map={},
            expected_value='from-env',
        )

    def test_does_provide_none_if_no_variable_exists_in_env_var_list(self):
        self.assert_chain_does_provide(
            service="batch",
            instance_map={},
            environ_map={},
            full_config_map={},
            scoped_config_map={},
            expected_value=None,
        )

    def test_does_provide_service_value_when_both_env_vars_exist(self):
        self.assert_chain_does_provide(
            service="batch",
            instance_map={},
            environ_map={
                'AWS_ENDPOINT_URL_BATCH': 'batch-endpoint-url',
                'AWS_ENDPOINT_URL': 'global-endpoint-url',
            },
            full_config_map={},
            scoped_config_map={},
            expected_value='batch-endpoint-url',
        )

    def test_does_provide_global_value_when_both_env_vars_exist(self):
        # Use a different service than the one set for the env variable
        self.assert_chain_does_provide(
            service="batch",
            instance_map={},
            environ_map={
                'AWS_ENDPOINT_URL_S3': 's3-endpoint-url',
                'AWS_ENDPOINT_URL': 'global-endpoint-url',
            },
            full_config_map={},
            scoped_config_map={},
            expected_value='global-endpoint-url',
        )

    def test_can_provide_global_config_var(self):
        full_config_map = {
            'profiles': {'default': {'endpoint_url': 'global-from-config'}}
        }

        scoped_config_map = full_config_map['profiles']['default']

        self.assert_chain_does_provide(
            service="ec2",
            instance_map={},
            environ_map={},
            full_config_map=full_config_map,
            scoped_config_map=scoped_config_map,
            expected_value='global-from-config',
        )

    def test_can_provide_service_config_var(self):

        full_config_map = {
            'profiles': {'default': {'services': 'my-services'}},
            'services': {
                'my-services': {
                    'batch': {'endpoint_url': 'global-from-config'}
                }
            },
        }

        scoped_config_map = full_config_map['profiles']['default']

        self.assert_chain_does_provide(
            service="batch",
            instance_map={},
            environ_map={},
            full_config_map=full_config_map,
            scoped_config_map=scoped_config_map,
            expected_value='global-from-config',
        )

    def test_can_provide_service_config_var_over_global(self):
        full_config_map = {
            'profiles': {
                'default': {
                    'services': 'my-services',
                    'endpoint_url': 'global-from-config',
                }
            },
            'services': {
                'my-services': {'batch': {'endpoint_url': "batch-from-config"}}
            },
        }

        scoped_config_map = full_config_map['profiles']['default']
        self.assert_chain_does_provide(
            service="batch",
            instance_map={},
            environ_map={},
            full_config_map=full_config_map,
            scoped_config_map=scoped_config_map,
            expected_value='batch-from-config',
        )

    def test_can_provide_service_config_var_over_global_diff_service(self):
        full_config_map = {
            'profiles': {
                'default': {
                    'services': 'my-services',
                    'endpoint_url': 'global-from-config',
                }
            },
            'services': {
                'my-services': {'batch': {'endpoint_url': "batch-from-config"}}
            },
        }

        scoped_config_map = full_config_map['profiles']['default']

        self.assert_chain_does_provide(
            service="s3",
            instance_map={},
            environ_map={},
            full_config_map=full_config_map,
            scoped_config_map=scoped_config_map,
            expected_value='global-from-config',
        )


@pytest.mark.parametrize(
    "service_name,service_id", _known_service_names_and_ids()
)
def test_service_env_var_name_is_correct(service_name, service_id):
    mocked_service_model = unittest.mock.Mock(spec=ServiceModel)
    mocked_service_model.service_id = service_id
    mocked_service_model.service_name = service_name

    chain = ConfiguredEndpointProviderChain(
        full_config={},
        scoped_config={},
        service_model=mocked_service_model,
        environ={},
    )
    transformed_service_id = service_id.upper().replace(" ", "_")
    expected_env_var_name = f'AWS_ENDPOINT_URL_{transformed_service_id}'
    assert chain._get_service_env_var_name() == expected_env_var_name
