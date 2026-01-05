from pathlib import Path

from pmc_monitor.pmc_protocol import ManagementTlv, Request, Response

from pmc_monitor import pmc_parser

DATA_DIR = Path(__file__).parent.absolute() / Path(__file__).stem


def pytest_generate_tests(metafunc):
    fixture_to_parametrize = "request_response_file"
    if fixture_to_parametrize not in metafunc.fixturenames:
        return

    request_response_pairs_dir = DATA_DIR / "request_response_pairs"
    assert request_response_pairs_dir.is_dir()

    test_cases = list(request_response_pairs_dir.glob("*.log"))
    metafunc.parametrize(fixture_to_parametrize, test_cases)


def test_request_response_parsing(request_response_file: Path):
    assert request_response_file.is_file()

    with open(request_response_file) as f:
        text = f.read()

    result = pmc_parser.parse(text)

    assert len(result) == 2
    request, response = result
    assert isinstance(request, Request)
    assert isinstance(response, Response)

    management_tlv_type = request_response_file.stem
    assert request.tlv_type == management_tlv_type
    assert isinstance(response.tlv, ManagementTlv)

    def canonicalize_tlv_name(name: str):
        """Convert `name` to UPPER_CASE"""
        return "".join(
            [
                "_" + char if char.isupper() and i > 0 else char
                for i, char in enumerate(name)
            ]
        ).upper()

    response_tlv_type = canonicalize_tlv_name(response.tlv.payload.__class__.__name__)
    assert response_tlv_type == management_tlv_type
