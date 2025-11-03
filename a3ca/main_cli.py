# /a3ca_project/main_cli.py
import click
import sys
import json
from pathlib import Path
from lxml import etree

# Import Layer 1
from parser.xsd_validator import validate_arxml, XSDValidatorError
from parser.arxml_parser import ARXMLParser

# Import Layer 2
from validation.validator import APValidator
from models.error_models import A3CAError, ErrorType # Cần A3CAError để bắt lỗi XSD

# Thiết lập đường dẫn gốc của dự án để import
sys.path.append(str(Path(__file__).parent))

@click.command()
@click.option(
    '--xsd', 'xsd_path',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Đường dẫn đến tệp XSD (ví dụ: AUTOSAR_AP_R19-11.xsd)."
)
@click.option(
    '--no-validate',
    is_flag=True,
    default=False,
    help="Bỏ qua bước xác thực XSD."
)
@click.argument(
    'arxml_files',
    # Chấp nhận 1 hoặc nhiều file. nargs=-1 có nghĩa là "tất cả"
    nargs=-1, 
    type=click.Path(exists=True, path_type=Path),
    required=True
)
def main(arxml_files: tuple[Path], xsd_path: Path, no_validate: bool):
    """
    A3CA Agent (Layer 1 & 2): Trình xác thực, phân tích cú pháp và
    kiểm tra ngữ nghĩa ARXML R19-11.
    """
    
    if not arxml_files:
        print("Lỗi: Không có tệp ARXML nào được chỉ định.", file=sys.stderr)
        sys.exit(1)

    # --- Layer 0: Xác thực Cú pháp (Syntactic Validation) ---
    if not no_validate:
        print(f"--- [Layer 0] Bắt đầu Xác thực XSD ---")
        try:
            for file_path in arxml_files:
                print(f"  Validating: {file_path.name}")
                validate_arxml(file_path, xsd_path)
            print("--- [Layer 0] Xác thực XSD Hoàn tất (Tất cả các tệp hợp lệ) ---")
        
        except (etree.DocumentInvalid, etree.XMLSyntaxError, XSDValidatorError) as e:
            print("\n!!! LỖI NGHIÊM TRỌNG: Xác thực cú pháp thất bại.", file=sys.stderr)
            print(f"Chi tiết: {e}", file=sys.stderr)
            
            # Sử dụng Error Model (Layer 2) để báo cáo lỗi cú pháp
            syntax_error = A3CAError(
                arxml_path=str(e.file) if hasattr(e, 'file') else "Unknown",
                autosar_version="Unknown", # Không thể parse phiên bản
                error_type=ErrorType.SYNTACTIC,
                description=f"XSD Validation Failed: {str(e)}",
                suggested_fix="Kiểm tra lại cấu trúc XML hoặc file XSD."
            )
            print(syntax_error.model_dump_json(indent=2))
            sys.exit(1)
    else:
        print("--- [Layer 0] (Đã bỏ qua Xác thực XSD) ---")

    # --- Layer 1: Phân tích cú pháp (Parsing) ---
    print("\n--- [Layer 1] Bắt đầu Phân tích cú pháp ARXML ---")
    try:
        parser = ARXMLParser()
        model = parser.parse_files(list(arxml_files))
        
    except etree.XMLSyntaxError as e:
        print("\n!!! LỖI NGHIÊM TRỌNG: Phân tích cú pháp thất bại.", file=sys.stderr)
        print(f"Chi tiết: {e}", file=sys.stderr)
        print("File có lỗi cú pháp. Dừng xử lý.", file=sys.stderr)
        sys.exit(1)
        
    print(f"--- [Layer 1] Phân tích cú pháp Hoàn tất. Phiên bản: {model.schema_version} ---")

    # --- Layer 2: Kiểm tra Ngữ nghĩa (Semantic Validation) ---
    print(f"\n--- [Layer 2] Bắt đầu Kiểm tra Ngữ nghĩa ---")
    validator_l2 = APValidator(model)
    validation_errors = validator_l2.run_validation()
    
    if validation_errors:
        print(f"\n!!! CẢNH BÁO: Phát hiện {len(validation_errors)} lỗi ngữ nghĩa (Layer 2):")
        # Chuyển đổi danh sách lỗi Pydantic thành JSON
        errors_json = [err.model_dump() for err in validation_errors]
        print(json.dumps(errors_json, indent=2, ensure_ascii=False))
    else:
        print("--- [Layer 2] Kiểm tra Ngữ nghĩa Hoàn tất (Validation PASSED) ---")

    # --- Xuất kết quả Layer 1 (Luôn chạy) ---
    print("\n--- A3CA Layer 1: Custom AP Model (JSON) ---")
    
    json_output = model.model_dump_json(indent=2)
    print(json_output)

if __name__ == "__main__":
    main()