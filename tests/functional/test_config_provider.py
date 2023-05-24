# Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
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
from pathlib import Path

import pytest

import botocore.exceptions
from botocore.config import Config
from botocore.session import get_session
from tests import mock

_SDK_DEFAULT_CONFIGURATION_VALUES_ALLOWLIST = (
    'retryMode',
    'stsRegionalEndpoints',
    's3UsEast1RegionalEndpoints',
    'connectTimeoutInMillis',
    'tlsNegotiationTimeoutInMillis',
)

session = get_session()
loader = session.get_component('data_loader')
sdk_default_configuration = loader.load_data('sdk-default-configuration')


@pytest.mark.parametrize("mode", sdk_default_configuration['base'])
def test_no_new_sdk_default_configuration_values(mode):
    err_msg = (
        f'New default configuration value {mode} introduced to '
        f'sdk-default-configuration.json. Support for setting {mode} must be '
        'considered and added to the DefaulConfigResolver. In addition, '
        'must add value to _SDK_DEFAULT_CONFIGURATION_VALUES_ALLOWLIST.'
    )
    assert mode in _SDK_DEFAULT_CONFIGURATION_VALUES_ALLOWLIST, err_msg


def test_default_configurations_resolve_correctly():
    session = get_session()
    config = Config(defaults_mode='standard')
    client = session.create_client(
        'sts', config=config, region_name='us-west-2'
    )
    assert client.meta.config.s3['us_east_1_regional_endpoint'] == 'regional'
    assert client.meta.config.connect_timeout == 3.1
    assert client.meta.endpoint_url == 'https://sts.us-west-2.amazonaws.com'
    assert client.meta.config.retries['mode'] == 'standard'


@pytest.fixture
def loader():
    test_models_dir = Path(__file__).parent / 'models'
    loader = botocore.loaders.Loader()
    loader.search_paths.insert(0, test_models_dir)
    return loader


@pytest.fixture
def session(loader):
    session = botocore.session.Session()
    session.register_component('data_loader', loader)
    return session


def config_store_updated(original_config_store, updated_config_store):
    return original_config_store is not updated_config_store


class TestSmartDefaultsConfigStoreFactory:
    @mock.patch('botocore.client.ClientCreator')
    def test_defaults_mode_resolved_from_config_store(
        self, client_creator, session
    ):
        config_store = session.get_component('config_store')
        config_store.set_config_variable('defaults_mode', 'standard')
        session.create_client('sts', 'us-west-2')
        assert (
            client_creator.call_args[0][-1].get_config_variable(
                "connect_timeout"
            )
            == 9999
        )
        assert config_store_updated(
            client_creator.call_args[0][-1], config_store
        )

    def test_no_mutate_session_provider(self, session):
        # Using the standard default mode should change the connect timeout
        # on the client, but not the session
        standard_client = session.create_client(
            'sts', 'us-west-2', config=Config(defaults_mode='standard')
        )
        assert standard_client.meta.config.connect_timeout == 9999.0
        assert session.get_config_variable('connect_timeout') is None

        # Using the legacy default mode should not change the connect timeout
        # on the client or the session. By default the connect timeout for a client
        # is 60 seconds, and unset on the session.
        legacy_client = session.create_client('sts', 'us-west-2')
        assert legacy_client.meta.config.connect_timeout == 60
        assert session.get_config_variable('connect_timeout') is None

    @mock.patch('botocore.client.ClientCreator')
    def test_defaults_mode_resolved_from_client_config(
        self, client_creator, session
    ):
        config = Config(defaults_mode='standard')
        session.create_client('sts', 'us-west-2', config=config)
        assert (
            client_creator.call_args[0][-1].get_config_variable(
                "connect_timeout"
            )
            == 9999
        )

    def test_defaults_mode_resolved_invalid_mode_exception(self, session):
        with pytest.raises(botocore.exceptions.InvalidDefaultsMode):
            config = Config(defaults_mode='foo')
            session.create_client('sts', 'us-west-2', config=config)

    @mock.patch(
        'botocore.session.SmartDefaultsConfigStoreFactory.merge_smart_defaults'
    )
    def test_defaults_mode_resolved_legacy(
        self, merge_smart_defaults, session
    ):
        session.create_client('sts', 'us-west-2')
        merge_smart_defaults.assert_not_called()
