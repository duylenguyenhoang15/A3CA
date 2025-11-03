# /a3ca_project/validation/validator.py
from typing import List, Dict, Set
from models.ap_model_r19_11 import APApplication
from models.error_models import A3CAError, ErrorType

class APValidator:
    """
    Thực thi các quy tắc kiểm tra ngữ nghĩa (Layer 2)
    trên mô hình đối tượng Pydantic (từ Layer 1).
    
    (CẬP NHẬT DEBUG LAYER 2)
    """
    def __init__(self, app_model: APApplication):
        self.app = app_model
        self.errors: List[A3CAError] = []
        self.version = app_model.schema_version or "R19-11"

        # Tạo các tập hợp (set) chứa AR-PATH của các tài nguyên
        # để kiểm tra tham chiếu nhanh hơn
        self.process_paths = set(self.app.process_definitions.keys())
        self.machine_paths = set(self.app.machines.keys())
        self.instance_paths = set(self.app.service_instances.keys())
        
        # Tạo tập hợp AR-PATH cho tất cả các Port (cả P và R)
        self.port_paths = set()
        for process in self.app.processes.values():
            self.port_paths.update(process.pports.keys())
            self.port_paths.update(process.rports.keys())
            
    def run_validation(self) -> List[A3CAError]:
        """
        Chạy tất cả các quy tắc kiểm tra ngữ nghĩa và trả về danh sách lỗi.
        """
        self.errors.clear()
        
        # Chạy các quy tắc kiểm tra
        self._check_service_instance_id_conflicts() # Sửa logic Lỗi 1
        self._check_dependency() # Lỗi 2 (Đã chạy đúng)
        self._check_broken_references() # Logic mới cho Lỗi 3, 4, 5
        self._check_r19_11_compliance() # Logic mới cho Lỗi 7
        
        # Ghi chú: Lỗi 6 (Logic mismatch) và Lỗi 7 (R19-11)
        # phức tạp hơn và sẽ cần các quy tắc chuyên biệt (chưa thêm)

        return self.errors

    def _check_service_instance_id_conflicts(self):
        """
        [Quy tắc 1 - ĐÃ SỬA] Kiểm tra Xung đột SERVICE-INSTANCE-ID.
        Phát hiện các 'service_instance_id' bị trùng lặp trong
        PROVIDED-SOMEIP-SERVICE-INSTANCE.
        """
        id_tracker: Dict[str, str] = {} # Key: service_instance_id, Value: ar_path
        
        for instance in self.app.service_instances.values():
            # Chỉ kiểm tra các instance được cung cấp (PROVIDED) và có ID
            if instance.direction == "PROVIDED" and instance.service_instance_id:
                service_id = instance.service_instance_id
                
                if service_id in id_tracker:
                    # Phát hiện trùng lặp!
                    original_path = id_tracker[service_id]
                    self.errors.append(A3CAError(
                        arxml_path=instance.ar_path,
                        autosar_version=self.version,
                        constraint_id="ARA_COM_UNIQUE_SERVICE_INSTANCE_ID", # ID tùy chỉnh
                        error_type=ErrorType.SEMANTIC,
                        description=(
                            f"Xung đột Service Instance ID: ID '{service_id}' "
                            f"bị trùng lặp. Đã được định nghĩa trước tại: {original_path}"
                        ),
                        suggested_fix=(
                            "Đảm bảo mỗi PROVIDED-SOMEIP-SERVICE-INSTANCE "
                            "có một SERVICE-INSTANCE-ID duy nhất."
                        )
                    ))
                else:
                    id_tracker[service_id] = instance.ar_path

    def _check_dependency(self):
        """
        [Quy tắc 2 - Giữ nguyên] Kiểm tra Dependency (Port Interface).
        Kiểm tra xem mọi R-PORT-PROTOTYPE có tham chiếu đến một
        SERVICE-INTERFACE mà được cung cấp bởi ít nhất một P-PORT-PROTOTYPE.
        """
        provided_interfaces: Set[str] = set()
        for process in self.app.processes.values():
            for pport in process.pports.values():
                provided_interfaces.add(pport.interface_ref)
        
        for process in self.app.processes.values():
            for rport in process.rports.values():
                if rport.interface_ref not in self.app.service_interfaces:
                    # Lỗi này đã được phát hiện (Lỗi 2)
                    self.errors.append(A3CAError(
                        arxml_path=rport.ar_path,
                        autosar_version=self.version,
                        constraint_id="ARA_COM_UNRESOLVED_DEPENDENCY",
                        error_type=ErrorType.SEMANTIC,
                        description=(
                            f"Không tìm thấy dependency: R-Port '{rport.short_name}' "
                            f"yêu cầu interface '{rport.interface_ref}' "
                            "nhưng interface này không được định nghĩa."
                        ),
                        suggested_fix=(
                            "Định nghĩa SERVICE-INTERFACE này hoặc sửa lại "
                            "REQUIRED-INTERFACE-TREF."
                        )
                    ))

    def _check_r19_11_compliance(self):
        """
        [Quy tắc MỚI] Kiểm tra vi phạm R19-11 (Lỗi 7).
        Cấm sử dụng tham chiếu 'MachineState' trong <PROCESS>.
        """
        for process in self.app.process_definitions.values():
            if process.machine_state_references:
                # Tìm thấy vi phạm
                first_violation_ref = process.machine_state_references[0]
                self.errors.append(A3CAError(
                    arxml_path=process.ar_path,
                    autosar_version=self.version,
                    constraint_id="R19_11_NO_MACHINE_STATE",
                    error_type=ErrorType.SEMANTIC,
                    description=(
                        f"Vi phạm R19-11: Process '{process.short_name}' "
                        f"tham chiếu đến 'MachineState' vốn đã bị loại bỏ. "
                        f"Tìm thấy tham chiếu: {first_violation_ref}"
                    ),
                    suggested_fix=(
                        "Xóa khối <STATE-DEPENDENT-STARTUP-CONFIGS> khỏi "
                        "Process hoặc thay đổi tham chiếu đến một Function Group hợp lệ."
                    )
                ))
    
    def _check_broken_references(self):
        """
        [Quy tắc MỚI] Kiểm tra các tham chiếu bị hỏng (Lỗi 3, 4, 5).
        Kiểm tra các mapping xem chúng có trỏ đến các đối tượng
        (Process, Machine, Port) thực sự tồn tại hay không.
        """
        
        # 1. Kiểm tra Process-to-Machine Mappings (Lỗi 4, 5)
        for mapping in self.app.process_mappings.values():
            if mapping.process_ref not in self.process_paths:
                self.errors.append(A3CAError(
                    arxml_path=mapping.ar_path,
                    autosar_version=self.version,
                    constraint_id="REF_DANGLING_PROCESS",
                    error_type=ErrorType.SEMANTIC,
                    description=(
                        f"Tham chiếu Process bị hỏng: PROCESS-REF "
                        f"'{mapping.process_ref}' không tồn tại."
                    ),
                    suggested_fix="Sửa PROCESS-REF trỏ đến một Process hợp lệ."
                ))
            
            if mapping.machine_ref not in self.machine_paths:
                self.errors.append(A3CAError(
                    arxml_path=mapping.ar_path,
                    autosar_version=self.version,
                    constraint_id="REF_DANGLING_MACHINE",
                    error_type=ErrorType.SEMANTIC,
                    description=(
                        f"Tham chiếu Machine bị hỏng: MACHINE-REF "
                        f"'{mapping.machine_ref}' không tồn tại."
                    ),
                    suggested_fix="Sửa MACHINE-REF trỏ đến một Machine hợp lệ."
                ))

        # 2. Kiểm tra Instance-to-Port Mappings (Lỗi 3)
        for mapping in self.app.instance_to_port_mappings.values():
            if mapping.instance_ref not in self.instance_paths:
                self.errors.append(A3CAError(
                    arxml_path=mapping.ar_path,
                    autosar_version=self.version,
                    constraint_id="REF_DANGLING_INSTANCE",
                    error_type=ErrorType.SEMANTIC,
                    description=(
                        f"Tham chiếu Instance bị hỏng: SERVICE-INSTANCE-REF "
                        f"'{mapping.instance_ref}' không tồn tại."
                    ),
                    suggested_fix="Sửa SERVICE-INSTANCE-REF trỏ đến một Service Instance hợp lệ."
                ))
            
            if mapping.port_ref not in self.port_paths:
                self.errors.append(A3CAError(
                    arxml_path=mapping.ar_path,
                    autosar_version=self.version,
                    constraint_id="REF_DANGLING_PORT",
                    error_type=ErrorType.SEMANTIC,
                    description=(
                        f"Tham chiếu Port bị hỏng: TARGET-PORT-PROTOTYPE-REF "
                        f"'{mapping.port_ref}' không tồn tại."
                    ),
                    suggested_fix="Sửa TARGET-PORT-PROTOTYPE-REF trỏ đến một Port Prototype hợp lệ."
                ))