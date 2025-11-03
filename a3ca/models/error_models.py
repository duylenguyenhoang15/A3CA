# /a3ca_project/models/error_models.py
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class ErrorType(str, Enum):
    """Phân loại lỗi."""
    SYNTACTIC = "SYNTACTIC"
    SEMANTIC = "SEMANTIC"
    OPTIMIZATION = "OPTIMIZATION"

class A3CAError(BaseModel):
    """
    Mô hình Pydantic chuẩn hóa cho một lỗi được phát hiện bởi A3CA.
    Dựa trên yêu cầu từ PDF.
    """
    arxml_path: str = Field(
        ...,
        description="Đường dẫn ARXML đầy đủ tới phần tử bị lỗi (nếu có thể xác định)."
    )
    autosar_version: str = Field(
        ...,
        description="Phiên bản ARXML đang được kiểm tra (ví dụ: R19-11)."
    )
    constraint_id: Optional[str] = Field(
        None,
        description="ID ràng buộc AUTOSAR bị vi phạm (Ví dụ: RS_EM_00123)."
    )
    error_type: ErrorType = Field(
        ...,
        description="Phân loại lỗi (Cú pháp, Ngữ nghĩa, Tối ưu hóa)."
    )
    description: str = Field(
        ...,
        description="Mô tả chi tiết lỗi ngữ nghĩa hoặc tối ưu hóa, lý do vi phạm."
    )
    suggested_fix: Optional[str] = Field(
        None,
        description="Đoạn cấu hình ARXML hoặc hướng dẫn cụ thể để sửa chữa lỗi."
    )