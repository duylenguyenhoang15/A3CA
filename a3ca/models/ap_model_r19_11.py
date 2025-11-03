# /a3ca_layer1/models/ap_model_r19_11.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# --- Mô hình Phần tử Cốt lõi ---

class BaseARElement(BaseModel):
    """Phần tử AUTOSAR cơ sở với các thuộc tính chung."""
    short_name: str
    ar_path: str # Đường dẫn AUTOSAR đầy đủ, duy nhất

class PortPrototype(BaseARElement):
    """
    Mô hình hóa một P-PORT-PROTOTYPE hoặc R-PORT-PROTOTYPE.
    (Fix v1.3: Sửa lỗi XPath)
    """
    direction: str # 'P' (Provided) hoặc 'R' (Required)
    interface_ref: str # AR-PATH đến ServiceInterface

class Process(BaseARElement):
    """
    Mô hình hóa một PROCESS.
    (Từ ADAPTIVE-APPLICATION-SW-COMPONENT-TYPE)
    """
    pports: Dict[str, PortPrototype] = Field(default_factory=dict)
    rports: Dict[str, PortPrototype] = Field(default_factory=dict)

class ProcessDefinition(BaseARElement):
    """Mô hình hóa một <PROCESS> và các cấu hình của nó."""
    machine_state_references: List[str] = Field(default_factory=list)

class ServiceInterface(BaseARElement):
    """Mô hình hóa một SERVICE-INTERFACE."""
    deployment_ref: Optional[str] = None

class ServiceInstance(BaseARElement):
    """
    Mô hình hóa PROVIDED-SOMEIP-SERVICE-INSTANCE hoặc
    REQUIRED-SOMEIP-SERVICE-INSTANCE.
    (Fix v1.3: Sửa tham chiếu)
    """
    # Thay vì interface_ref, chúng ta tham chiếu đến deployment
    deployment_ref: str 
    direction: str # 'PROVIDED' hoặc 'REQUIRED'
    service_instance_id: Optional[str] = None

# --- Mô hình Deployment (Triển khai) ---

class ServiceDeployment(BaseARElement):
    """
    Mô hình hóa SOMEIP-SERVICE-INTERFACE-DEPLOYMENT.
    """
    service_id: str
    service_interface_ref: str 
    methods: Dict[str, str] = Field(default_factory=dict) 
    events: Dict[str, str] = Field(default_factory=dict)

# --- Mô hình Machine & Linking (Cập nhật v1.3) ---

class NetworkEndpoint(BaseARElement):
    """
    Mô hình mới (v1.3) để chứa thông tin IP
    (Từ NETWORK-ENDPOINT)
    """
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    gateway: Optional[str] = None

class MachineDesign(BaseARElement):
    """
    Mô hình mới (v1.3) để liên kết Machine với Endpoint
    (Từ MACHINE-DESIGN)
    """
    # Tham chiếu đến UNICAST-NETWORK-ENDPOINT-REF
    network_endpoint_ref: Optional[str] = None 

class Machine(BaseARElement):
    """
    Mô hình hóa một MACHINE.
    (Cập nhật v1.3: Thông tin IP sẽ được điền sau khi linking)
    """
    # Các trường này sẽ được điền bởi trình parser sau khi linking
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    gateway: Optional[str] = None
    
    # Tham chiếu dùng để linking (không xuất ra JSON nếu không cần)
    machine_design_ref: Optional[str] = Field(None, exclude=True)

# --- Mô hình Mappings (Ánh xạ) ---

class ProcessToMachineMapping(BaseARElement):
    """Mô hình hóa PROCESS-TO-MACHINE-MAPPING."""
    process_ref: str 
    machine_ref: str 

class ServiceInstanceToMachineMapping(BaseARElement):
    """
    Mô hình hóa SOMEIP-SERVICE-INSTANCE-TO-MACHINE-MAPPING.
    (Fix v1.3: Sửa XPath port)
    """
    instance_ref: str 
    machine_ref: str 
    tcp_port: Optional[int] = None
    udp_port: Optional[int] = None

class ServiceInstanceToPortMapping(BaseARElement):
    """Mô hình hóa SERVICE-INSTANCE-TO-PORT-PROTOTYPE-MAPPING."""
    instance_ref: str 
    port_ref: str 

# --- Mô hình Gốc ---

class APApplication(BaseModel):
    """
    Mô hình Pydantic gốc (v1.3).
    """
    schema_version: Optional[str] = None
    
    # Danh mục các phần tử chính
    processes: Dict[str, Process] = Field(default_factory=dict)
    process_definitions: Dict[str, ProcessDefinition] = Field(default_factory=dict)
    service_interfaces: Dict[str, ServiceInterface] = Field(default_factory=dict)
    service_instances: Dict[str, ServiceInstance] = Field(default_factory=dict)
    machines: Dict[str, Machine] = Field(default_factory=dict)
    deployments: Dict[str, ServiceDeployment] = Field(default_factory=dict)
    
    # Danh mục các ánh xạ
    process_mappings: Dict[str, ProcessToMachineMapping] = Field(default_factory=dict)
    instance_to_machine_mappings: Dict[str, ServiceInstanceToMachineMapping] = Field(default_factory=dict)
    instance_to_port_mappings: Dict[str, ServiceInstanceToPortMapping] = Field(default_factory=dict)

    # Các đối tượng trung gian (dùng để linking, không xuất ra JSON)
    network_endpoints: Dict[str, NetworkEndpoint] = Field(default_factory=dict, exclude=True)
    machine_designs: Dict[str, MachineDesign] = Field(default_factory=dict, exclude=True)
    
    # Bỏ qua theo yêu cầu
    execution_manifests: Dict[str, str] = Field(default_factory=dict, exclude=True)