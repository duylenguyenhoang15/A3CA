# /a3ca_project/tests/test_validator.py
import pytest
from pathlib import Path
from models.ap_model_r19_11 import APApplication
from parser.arxml_parser import ARXMLParser # Giả định từ Layer 1
from validation.validator import APValidator

# Đường dẫn đến thư mục data, giả định file test chạy từ thư mục gốc
BASE_DATA_PATH = Path(__file__).parent.parent / "data"

@pytest.fixture(scope="module")
def valid_app() -> APApplication:
    """Fixture tải và parse một tệp ARXML được cho là hợp lệ."""
    # Giả định tệp test_case_01.arxml là một tệp hợp lệ
    # và parser của bạn hoạt động chính xác
    valid_file = BASE_DATA_PATH / "arxml_inputs" / "test_case_01.arxml"
    
    # Bỏ qua test nếu không tìm thấy file
    if not valid_file.exists():
        pytest.skip("Không tìm thấy tệp test_case_01.arxml hợp lệ để test validator")
        
    parser = ARXMLParser(valid_file)
    app_model = parser.parse()
    return app_model

@pytest.fixture(scope="module")
def conflict_app() -> APApplication:
    """Fixture tải và parse tệp ARXML có lỗi xung đột ID."""
    invalid_file = BASE_DATA_PATH / "arxml_invalid_semantic" / "id_conflict.arxml"
    
    if not invalid_file.exists():
        pytest.skip("Không tìm thấy tệp id_conflict.arxml để test validator")
        
    parser = ARXMLParser(invalid_file)
    app_model = parser.parse()
    return app_model

def test_validator_with_valid_file(valid_app: APApplication):
    """
    Kiểm tra trình xác thực với một tệp hợp lệ,
    mong đợi không có lỗi ngữ nghĩa.
    """
    validator = APValidator(valid_app)
    errors = validator.run_validation()
    
    # Giả định tệp test_case_01.arxml không có lỗi dependency hoặc ID
    assert len(errors) == 0, "Tệp hợp lệ không nên có lỗi ngữ nghĩa"

def test_validator_id_conflict(conflict_app: APApplication):
    """
    Kiểm tra trình xác thực với tệp id_conflict.arxml,
    mong đợi phát hiện lỗi trùng lặp ID.
    """
    validator = APValidator(conflict_app)
    errors = validator.run_validation()
    
    assert len(errors) > 0, "Phải phát hiện ít nhất một lỗi"
    
    # Tìm lỗi xung đột ID
    id_conflict_error = next(
        (err for err in errors if err.constraint_id == "ARA_COM_UNIQUE_SERVICE_ID"), 
        None
    )
    
    assert id_conflict_error is not None, "Phải tìm thấy lỗi 'ARA_COM_UNIQUE_SERVICE_ID'"
    assert id_conflict_error.error_type == "SEMANTIC"
    assert "Xung đột Service ID: ID '100'" in id_conflict_error.description
    assert "Deployment_B_Conflict" in id_conflict_error.arxml_path

def test_validator_dependency_check(valid_app: APApplication, monkeypatch):
    """
    Kiểm tra logic kiểm tra dependency bằng cách "giả mạo" một lỗi.
    """
    # Tạo một R-Port "mới" tham chiếu đến một interface không tồn tại
    class MockRPort:
        ar_path = "/Mock/Process/R_Missing"
        short_name = "R_Missing"
        interface_ref = "/Interfaces/IDoNotExist"

    # Thêm R-Port giả mạo vào process đầu tiên (nếu có)
    if valid_app.processes:
        first_process_key = next(iter(valid_app.processes))
        valid_app.processes[first_process_key].rports["R_Missing"] = MockRPort()

    validator = APValidator(valid_app)
    errors = validator.run_validation()
    
    dependency_error = next(
        (err for err in errors if err.constraint_id == "ARA_COM_UNRESOLVED_DEPENDENCY"), 
        None
    )
    
    assert dependency_error is not None, "Phải tìm thấy lỗi dependency"
    assert "Không tìm thấy dependency" in dependency_error.description
    assert "/Interfaces/IDoNotExist" in dependency_error.description