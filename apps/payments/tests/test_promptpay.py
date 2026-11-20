import pytest

from apps.payments import promptpay


def test_crc_matches_ccitt_false_check_value():
    assert promptpay.crc16_ccitt("123456789") == "29B1"


def test_mobile_payload_with_amount():
    payload = promptpay.build_payload("081-234-5678", 49900)

    assert payload.startswith("000201010212")  # dynamic QR because it has an amount
    assert "0113006681234567" in payload  # 0066 + number without leading zero
    assert "5406499.00" in payload
    assert payload[-8:-4] == "6304"
    assert payload[-4:] == promptpay.crc16_ccitt(payload[:-4])


def test_tax_id_payload_without_amount():
    payload = promptpay.build_payload("0105556012345", None)

    assert payload.startswith("000201010211")
    assert "02130105556012345" in payload
    assert "54" not in payload.split("5303764")[1].split("5802")[0]


@pytest.mark.parametrize("bad", ["", "12345", "08123456789", "abc"])
def test_invalid_ids_are_refused(bad):
    with pytest.raises(ValueError):
        promptpay.build_payload(bad, 100)


def test_svg_is_inline_ready():
    svg = promptpay.render_svg(promptpay.build_payload("0812345678", 100))

    assert svg.startswith("<svg")
    assert "<?xml" not in svg
    assert "style=" not in svg  # CSP forbids inline styles
