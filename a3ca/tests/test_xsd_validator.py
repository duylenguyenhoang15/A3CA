# /a3ca_layer1/tests/test_xsd_validator.py
import pytest
from pathlib import Path
from lxml import etree
from parser.xsd_validator import validate_arxml, XSDValidatorError

# Giả sử thư mục gốc là 'a3ca_layer1' khi chạy pytest
BASE_DIR = Path(__file__).parent.parent
XSD_FILE = BASE_DIR / "data/xsd/AUTOSAR_00048.xsd"
VALID_ARXML = BASE_DIR / "data/arxml_inputs/Machine.arxml"
INVALID_ARXML = BASE_DIR / "data/invalid_syntax.arxml" # Lỗi cú pháp XML
NON_CONFORMING_ARXML = BASE_DIR / "data/arxml_inputs/iamdesign.arxml" # Hợp lệ XML, nhưng có thể thiếu elem so với XSD (tùy XSD)

def test_validator_paths():
    """Kiểm tra xem các tệp test có tồn tại không."""
    assert XSD_FILE.exists(), "Tệp XSD không tồn tại"
    assert VALID_ARXML.exists(), "Tệp ARXML hợp lệ không tồn tại"
    assert INVALID_ARXML.exists(), "Tệp ARXML không hợp lệ không tồn tại"

def test_validation_pass():
    """
    Test case cho tệp ARXML hợp lệ.
    Hàm validate_arxml() phải trả về True và không ném ra exception.
    """
    # Sử dụng tệp Machine.arxml (hoặc bất kỳ tệp nào trong arxml_inputs)
    try:
        assert validate_arxml(VALID_ARXML, XSD_FILE) == True
    except Exception as e:
        pytest.fail(f"Xác thực thất bại không mong muốn: {e}")

def test_validation_fail_syntax_error():
    """
    Test case cho tệp ARXML không hợp lệ (lỗi cú pháp).
    Phải ném ra XSDValidatorError (do lxml.etree.XMLSyntaxError).
    """
    with pytest.raises((XSDValidatorError, etree.XMLSyntaxError)):
        validate_arxml(INVALID_ARXML, XSD_FILE)

# Lưu ý: Để test lỗi logic (DocumentInvalid) cần một tệp ARXML
# có cú pháp XML đúng, nhưng vi phạm schema (ví dụ: thẻ sai vị trí).
# Tệp invalid_syntax.arxml của chúng ta là lỗi cú pháp (XMLSyntaxError).
# Cả hai đều là trường hợp thất bại hợp lệ cho validator.