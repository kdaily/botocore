import json
from pathlib import Path
from unittest import mock

import pytest
from pytest import fixture

import botocore.configprovider
from botocore.compat import urlsplit
from tests import ClientHTTPStubber, temporary_file

ENDPOINT_TESTDATA_FILE = Path(__file__).parent / 'data' \
    / "configured-endpoint-urls" / "test-cases" / "profile-tests.json"

with open(ENDPOINT_TESTDATA_FILE) as f:
    data = json.load(f)
    suites = data.get('testSuites', {})
    ENDPOINT_TEST_SUITE = suites[0]


def dict_to_ini_section(ini_dict, section_header):
    profile_str = f'[{section_header}]\n'
    for key, value in ini_dict.items():
        if isinstance(value, dict):
            profile_str += f"{key} =\n"
            for new_key, new_value in value.items():
                profile_str += f"  {new_key}={new_value}\n"
        else:
            profile_str += f"{key}={value}\n"
    return profile_str + "\n"


def create_cases(test_suite):
    profiles = test_suite['profiles']
    service_sections = test_suite['services']
    environments = test_suite['environments']
    client_configs = test_suite['client_configs']
    tests = test_suite['endpointUrlTests']

    for test in tests:
        new_test = test.copy()

        data_to_add = {}
        environment_name = test.get('environment', None)
        environment = environments.get(environment_name, {})
        data_to_add['environment'] = environment

        client_config_name = test.get('client_config', None)
        client_config = client_configs.get(client_config_name, {})
        data_to_add['client_config'] = client_config

        profile_name = test.get('profile', None)
        profile = profiles.get(profile_name, {})
        data_to_add['profile'] = profile

        service_section_name = profile.get('services', None)
        service_section = service_sections.get(service_section_name, {})
        data_to_add['services'] = service_section

        new_test['augmented_data'] = data_to_add
        yield new_test


def _normalize_endpoint(url):
    split_endpoint = urlsplit(url)
    actual_endpoint = f"{split_endpoint.scheme}://{split_endpoint.netloc}"
    return actual_endpoint


def assert_endpoint_url_used(client, operation, params, expected_endpoint_url):
    http_stubber = ClientHTTPStubber(client)
    http_stubber.start()
    http_stubber.add_response()

    assert client.meta.endpoint_url == expected_endpoint_url

    # Call an operation on the client
    getattr(client, operation)(**params)

    assert (
        _normalize_endpoint(http_stubber.requests[0].url)
        == expected_endpoint_url
    )


def idfn(test_case):
    return test_case['name']


def setup_configuration_environment(test_case):
    profile_str = dict_to_ini_section(
        test_case['augmented_data']['profile'],
        section_header=f"profile {test_case['profile']}",
    )
    services_section_name = test_case['augmented_data']['profile'].get(
        'services', None
    )
    service_section_str = dict_to_ini_section(
        test_case['augmented_data']['services'],
        section_header=f'services {services_section_name}',
    )
    test_case['augmented_data']['profile_string'] = (
        profile_str + service_section_str
    )


def get_client(test_case):
    botocore_session = botocore.session.get_session()
    # need to update the environment with the path to
    # the temp config file
    with temporary_file('w') as f, mock.patch.dict(
        botocore.configprovider.os.environ,
        dict(
            **test_case['augmented_data']['environment'],
            **{"AWS_CONFIG_FILE": f.name},
        ),
        clear=True,
    ) as mockenv:  ## noqa

        f.write(test_case['augmented_data']['profile_string'])
        f.flush()

        botocore_session.set_config_variable('profile', test_case['profile'])

        client = botocore_session.create_client(
            test_case['service'],
            **test_case['augmented_data']['client_config'],
        )

        return client


@pytest.mark.parametrize(
    "test_case", create_cases(ENDPOINT_TEST_SUITE), ids=idfn
)
def test_resolve_configured_endpoint_url(test_case):
    setup_configuration_environment(test_case)
    client = get_client(test_case)
    assert_endpoint_url_used(
        client=client,
        operation="list_objects",
        params={"Bucket": "Foo"},
        expected_endpoint_url=test_case['output']['endpointUrl'],
    )
