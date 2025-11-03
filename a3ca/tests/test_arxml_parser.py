# /a3ca_layer1/tests/test_arxml_parser.py
import pytest
import glob
from pathlib import Path
from parser.arxml_parser import ARXMLParser
from models.ap_model_r19_11 import APApplication

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data/arxml_inputs"

# Tự động tìm tất cả 10 tệp ARXML trong thư mục
# (Sử dụng list() để thực thi glob ngay lập tức)
ALL_ARXML_FILES = list(DATA_DIR.glob("*.arxml"))

# Đảm bảo chúng ta tìm thấy tất cả 10 tệp
assert len(ALL_ARXML_FILES) == 10, \
    f"Chỉ tìm thấy {len(ALL_ARXML_FILES)} tệp, dự kiến 10 tệp ARXML"

@pytest.mark.parametrize("arxml_file_path", ALL_ARXML_FILES)
def test_parse_single_file_successfully(arxml_file_path: Path):
    """
    Test (sử dụng parametrize) rằng mỗi tệp ARXML có thể được 
    phân tích cú pháp riêng lẻ mà không gây lỗi.
    """
    parser = ARXMLParser()
    try:
        model = parser.parse_files([arxml_file_path])
        
        assert model is not None
        assert isinstance(model, APApplication)
        assert model.schema_version is not None, "Không phát hiện được schema version"
        
    except Exception as e:
        pytest.fail(
            f"Parser thất bại khi xử lý tệp '{arxml_file_path.name}': {e}"
        )

def test_parse_all_files_together():
    """
    Test trường hợp gộp (merge) tất cả 10 tệp ARXML
    vào một mô hình Pydantic duy nhất.
    """
    parser = ARXMLParser()
    model = parser.parse_files(ALL_ARXML_FILES)
    
    assert model is not None
    assert isinstance(model, APApplication)
    
    # Kiểm tra xem dữ liệu đã được tổng hợp từ nhiều tệp
    # (Dựa trên nội dung các tệp ARXML của bạn)
    assert len(model.processes) > 0, "Không parse được Process nào"
    assert len(model.service_interfaces) > 0, "Không parse được Service Interface nào"
    assert len(model.execution_manifests) > 0, "Không parse được Execution Manifest nào"
    assert len(model.service_instances) > 0, "Không parse được Service Instance nào"

    # Kiểm tra một tham chiếu cụ thể (ví dụ)
    assert "/iam/swc/executable/IAMApp01" in model.processes
    assert "/iam/service/ServiceInterfaceIAMService01" in model.service_interfaces