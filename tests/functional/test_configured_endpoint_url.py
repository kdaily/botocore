import json
from pathlib import Path
from unittest import mock

import pytest
from pytest import fixture

from botocore.compat import urlsplit
import botocore.configprovider
from tests import (
    temporary_file,
    ClientHTTPStubber,
)
ENDPOINT_TESTDATA_FILE = Path(__file__).parent / 'data' / "profile-tests.json"

with open(ENDPOINT_TESTDATA_FILE) as f:
    data = json.load(f)
    suites = data.get('testSuites', {})
    ENDPOINT_TEST_CASES = suites[1]

def dict_to_ini_section(ini_dict, section_name, name):
    profile_str = f'[{section_name} {name}]\n'
    for key, value in ini_dict.items():
        if isinstance(value, dict):
            profile_str += f"{key} =\n"
            for new_key, new_value in value.items():
                profile_str += f"  {new_key}={new_value}\n"
        else:
            profile_str += f"{key}={value}\n"
    return profile_str + "\n"


def create_cases(cases):
    data = cases
    profiles = data['profiles']
    service_sections = data['services']
    tests = data['endpointUrlTests']
    new_tests = []
    for test in tests:
        new_test = test.copy()
        profile_name = test.get('profile', None)
        profile = profiles.get(profile_name, {})
        service_section_name = profile.get('services', None)
        service_section = service_sections.get(service_section_name, {})
        profile_str = dict_to_ini_section(
            profile, section_name="profile", name=profile_name)
        service_section_str = dict_to_ini_section(
            service_section, section_name='services', 
            name=service_section_name)
        combined_profile_str = profile_str + service_section_str
        new_test.update({'profile_string': combined_profile_str})
        new_tests.append(new_test)
    return new_tests


def parametrize_test_cases(cases):
    cases = create_cases(cases)
    return pytest.mark.parametrize(
        "test_case",
        cases,
        ids=[c["name"] for c in cases],
    )

@fixture
def mock_botocore_session():
    return botocore.session.get_session()


def assert_endpoint(request, expected_endpoint):
    split_endpoint = urlsplit(request.url)
    print(split_endpoint)
    actual_endpoint = f"{split_endpoint.scheme}://{split_endpoint.netloc}"
    # if split_endpoint.path[0] == "/":
    #     actual_endpoint += split_endpoint.path[0]
    assert actual_endpoint == expected_endpoint

@parametrize_test_cases(ENDPOINT_TEST_CASES)
@pytest.mark.parametrize("client_config", [True, False])
def test_resolve_custom_endpoint_url(
    test_case,
    client_config,
    mock_botocore_session):
        environment = test_case.get('environment', {})

        # need to update the environment with the path to
        # the temp config file
        with temporary_file('w') as f, \
            mock.patch.dict(
                botocore.configprovider.os.environ,
                dict(**environment, **{"AWS_CONFIG_FILE": f.name}),
                clear=True) as mockenv:

            f.write(test_case['profile_string'])
            f.flush()

            mock_botocore_session.set_config_variable(
                'profile', test_case['profile']
            )

            if client_config:
                output_url = "https://clientconfig.endpoint.aws"
                client = mock_botocore_session.create_client(
                    test_case['service'], endpoint_url=output_url)
            else:
                client = mock_botocore_session.create_client(
                    test_case['service'])
                output_url = test_case['output']['endpointUrl']

            http_stubber = ClientHTTPStubber(client)
            http_stubber.start()

            assert client.meta.endpoint_url == output_url

            http_stubber.add_response()
            client.list_objects(Bucket="foo")
            assert_endpoint(http_stubber.requests[0], output_url)
