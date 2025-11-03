# /a3ca_layer1/parser/arxml_parser.py
import sys
import warnings
from pathlib import Path
from typing import List, Dict, Any, Optional
from lxml import etree
from models.ap_model_r19_11 import (
    APApplication, Process, ServiceInterface, 
    ServiceInstance, PortPrototype, Machine, ServiceDeployment,
    ProcessToMachineMapping, ServiceInstanceToMachineMapping,
    ServiceInstanceToPortMapping, NetworkEndpoint, MachineDesign,
    ProcessDefinition
)

NS_MAP_KEY = 'default' 

class ARXMLParser:
    """
    Trình phân tích cú pháp v1.3: Sửa lỗi XPath cho Ports, Instances,
    và thêm logic linking cho Machine IP.
    """
    
    def __init__(self):
        self.model = APApplication()
        self._ns_map: Dict[str, str] = {}
        self._schema_version_detected: Optional[str] = None

    def _get_ar_path(self, element: etree._Element) -> str:
        parts = []
        current = element
        while current is not None:
            tag = etree.QName(current.tag).localname
            if tag == 'AR-PACKAGE' or 'SHORT-NAME' in [
                etree.QName(child.tag).localname for child in current
            ]:
                short_name_elem = current.find(f"{NS_MAP_KEY}:SHORT-NAME", self._ns_map)
                if short_name_elem is not None and short_name_elem.text:
                    parts.append(short_name_elem.text)
            
            if tag == 'AUTOSAR':
                break
            
            current = current.getparent()
            
        return '/' + '/'.join(reversed(parts))

    def _detect_version_and_ns(self, root: etree._Element):
        self._ns_map = {
            NS_MAP_KEY if k is None else k: v 
            for k, v in root.nsmap.items()
        }
        
        schema_loc = root.attrib.get(
            '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', ''
        )
        
        if 'AUTOSAR_00048.xsd' in schema_loc or 'r19-11' in schema_loc.lower():
            self._schema_version_detected = "R19-11"
        else:
            parts = [p for p in schema_loc.split() if 'autosar.org' in p or 'AUTOSAR' in p]
            self._schema_version_detected = parts[0] if parts else "Unknown"

        if self.model.schema_version is None:
            self.model.schema_version = self._schema_version_detected
        
        if self._schema_version_detected != "R19-11":
            warnings.warn(
                f"Phát hiện phiên bản '{self._schema_version_detected}'. "
                f"Layer 1 này được tối ưu cho R19-11."
            )

    def parse_files(self, arxml_paths: List[Path]) -> APApplication:
        print(f"[Parser] Bắt đầu phân tích {len(arxml_paths)} tệp...", file=sys.stderr)
        
        for file_path in arxml_paths:
            print(f"   [Parser] Đang xử lý '{file_path.name}'...", file=sys.stderr)
            try:
                tree = etree.parse(str(file_path))
                root = tree.getroot()
                
                if not self._ns_map:
                    self._detect_version_and_ns(root)
                
                self._parse_elements(root)

            except etree.XMLSyntaxError as e:
                raise e
            except OSError as e:
                print(f"LỖI: Lỗi I/O khi đọc {file_path.name}: {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"LỖI: Lỗi không xác định khi parse {file_path.name}: {e}", file=sys.stderr)
                continue

        # Thực hiện linking (liên kết) sau khi parse
        self._link_deployments()
        self._link_machine_ips() # <--- FIX v1.3

        print(f"[Parser] Hoàn tất. Tìm thấy:", file=sys.stderr)
        print(f"   - {len(self.model.processes)} Processes (với {sum(len(p.pports) + len(p.rports) for p in self.model.processes.values())} ports)")
        print(f"   - {len(self.model.service_interfaces)} Service Interfaces")
        print(f"   - {len(self.model.service_instances)} Service Instances (Provided/Required)")
        print(f"   - {len(self.model.machines)} Machines (Đã liên kết IP)")
        print(f"   - {len(self.model.deployments)} Service Deployments")
        print(f"   - {len(self.model.process_definitions)} Process Definitions")
        print(f"   - {len(self.model.process_mappings)} Process Mappings")
        print(f"   - {len(self.model.instance_to_machine_mappings)} Instance-to-Machine Mappings")
        print(f"   - {len(self.model.instance_to_port_mappings)} Instance-to-Port Mappings")
        
        return self.model

    def _link_deployments(self):
        """Liên kết ServiceInterface với Deployment (nếu có)."""
        for deploy_path, deploy in self.model.deployments.items():
            if deploy.service_interface_ref in self.model.service_interfaces:
                self.model.service_interfaces[deploy.service_interface_ref].deployment_ref = deploy_path

    def _link_machine_ips(self):
        """
        FIX v1.3: Liên kết Machine -> MachineDesign -> NetworkEndpoint -> IP.
        """
        print(f"   [Parser] Đang liên kết IP cho Machines...", file=sys.stderr)
        for machine in self.model.machines.values():
            if machine.machine_design_ref in self.model.machine_designs:
                design = self.model.machine_designs[machine.machine_design_ref]
                if design.network_endpoint_ref in self.model.network_endpoints:
                    endpoint = self.model.network_endpoints[design.network_endpoint_ref]
                    
                    machine.ip_address = endpoint.ip_address
                    machine.netmask = endpoint.netmask
                    machine.gateway = endpoint.gateway

    def _get_text(self, elem, xpath_str: str) -> Optional[str]:
        """Helper để tìm text an toàn."""
        found = elem.findtext(xpath_str, namespaces=self._ns_map)
        return found if found else None

    def _parse_elements(self, root: etree._Element):
        """Sử dụng XPath để tìm và parse TẤT CẢ các phần tử v1.3."""
        
        # 1. Processes và Ports (FIX v1.3)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:ADAPTIVE-APPLICATION-SW-COMPONENT-TYPE", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            if sn:
                if path not in self.model.processes:
                    self.model.processes[path] = Process(short_name=sn, ar_path=path)
                
                # Parse P-Ports (FIX v1.3: Dùng PROVIDED-INTERFACE-TREF)
                for port_elem in elem.xpath(f".//{NS_MAP_KEY}:P-PORT-PROTOTYPE", namespaces=self._ns_map):
                    port_sn = self._get_text(port_elem, f"{NS_MAP_KEY}:SHORT-NAME")
                    port_path = self._get_ar_path(port_elem)
                    port_if_ref = self._get_text(port_elem, f".//{NS_MAP_KEY}:PROVIDED-INTERFACE-TREF") # <-- Đã sửa
                    if port_sn and port_path and port_if_ref and port_path not in self.model.processes[path].pports:
                        self.model.processes[path].pports[port_path] = PortPrototype(
                            short_name=port_sn, ar_path=port_path, direction='P', interface_ref=port_if_ref
                        )

                # Parse R-Ports (FIX v1.3: Dùng REQUIRED-INTERFACE-TREF)
                for port_elem in elem.xpath(f".//{NS_MAP_KEY}:R-PORT-PROTOTYPE", namespaces=self._ns_map):
                    port_sn = self._get_text(port_elem, f"{NS_MAP_KEY}:SHORT-NAME")
                    port_path = self._get_ar_path(port_elem)
                    port_if_ref = self._get_text(port_elem, f".//{NS_MAP_KEY}:REQUIRED-INTERFACE-TREF") # <-- Đã sửa
                    if port_sn and port_path and port_if_ref and port_path not in self.model.processes[path].rports:
                        self.model.processes[path].rports[port_path] = PortPrototype(
                            short_name=port_sn, ar_path=port_path, direction='R', interface_ref=port_if_ref
                        )

        # 2. Service Interfaces
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:SERVICE-INTERFACE", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            if sn and path not in self.model.service_interfaces:
                self.model.service_interfaces[path] = ServiceInterface(short_name=sn, ar_path=path)
        
        # 3. Execution Manifests (Bỏ qua theo yêu cầu)
        # (Không có vòng lặp)
        
        # 4. Service Instances (FIX v1.3, CẬP NHẬT DEBUG LAYER 2)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:PROVIDED-SOMEIP-SERVICE-INSTANCE | //*/{NS_MAP_KEY}:REQUIRED-SOMEIP-SERVICE-INSTANCE", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            # FIX v1.3: Tham chiếu đến DEPLOYMENT, không phải INTERFACE
            deploy_ref = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INTERFACE-DEPLOYMENT-REF") 
            direction = 'PROVIDED' if 'PROVIDED' in etree.QName(elem.tag).localname else 'REQUIRED'
            
            # --- CẬP NHẬT: Bắt đầu ---
            # Lấy Service Instance ID (thường chỉ có ở PROVIDED instances)
            instance_id = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INSTANCE-ID")
            # --- CẬP NHẬT: Kết thúc ---
            
            if sn and path not in self.model.service_instances and deploy_ref:
                self.model.service_instances[path] = ServiceInstance(
                    short_name=sn, 
                    ar_path=path, 
                    deployment_ref=deploy_ref, 
                    direction=direction,
                    service_instance_id=instance_id # <-- CẬP NHẬT: Thêm tham số
                )

        # 5. Machines (FIX v1.3: Chỉ parse tham chiếu)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:MACHINE", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            if sn and path not in self.model.machines:
                # FIX v1.3: Lấy tham chiếu để linking sau
                design_ref = self._get_text(elem, f".//{NS_MAP_KEY}:MACHINE-DESIGN-REF")
                
                self.model.machines[path] = Machine(
                    short_name=sn, ar_path=path, machine_design_ref=design_ref
                )

        # 6. Service Deployments (Đã đúng)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:SOMEIP-SERVICE-INTERFACE-DEPLOYMENT", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            if_ref = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INTERFACE-REF")
            service_id = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INTERFACE-ID")
            
            if sn and path not in self.model.deployments and if_ref and service_id:
                deploy = ServiceDeployment(short_name=sn, ar_path=path, service_id=service_id, service_interface_ref=if_ref)
                
                for m_elem in elem.xpath(f".//{NS_MAP_KEY}:METHOD-DEPLOYMENTS/{NS_MAP_KEY}:SOMEIP-METHOD-DEPLOYMENT", namespaces=self._ns_map):
                    m_ref = self._get_text(m_elem, f".//{NS_MAP_KEY}:METHOD-REF")
                    m_id = self._get_text(m_elem, f".//{NS_MAP_KEY}:METHOD-ID")
                    if m_ref and m_id:
                        deploy.methods[m_ref.split('/')[-1]] = m_id

                for e_elem in elem.xpath(f".//{NS_MAP_KEY}:EVENT-DEPLOYMENTS/{NS_MAP_KEY}:SOMEIP-EVENT-DEPLOYMENT", namespaces=self._ns_map):
                    e_ref = self._get_text(e_elem, f".//{NS_MAP_KEY}:EVENT-REF")
                    e_id = self._get_text(e_elem, f".//{NS_MAP_KEY}:EVENT-ID")
                    if e_ref and e_id:
                        deploy.events[e_ref.split('/')[-1]] = e_id 
                
                self.model.deployments[path] = deploy

        # 7. Mappings
        # 7a. Process-to-Machine (Đã đúng)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:PROCESS-TO-MACHINE-MAPPING", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            proc_ref = self._get_text(elem, f".//{NS_MAP_KEY}:PROCESS-REF")
            mach_ref = self._get_text(elem, f".//{NS_MAP_KEY}:MACHINE-REF")
            if sn and path not in self.model.process_mappings and proc_ref and mach_ref:
                self.model.process_mappings[path] = ProcessToMachineMapping(
                    short_name=sn, ar_path=path, process_ref=proc_ref, machine_ref=mach_ref
                )

        # 7b. Instance-to-Machine (FIX v1.3: Sửa XPath port)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:SOMEIP-SERVICE-INSTANCE-TO-MACHINE-MAPPING", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            # Chú ý: SERVICE-INSTANCE-REFS (số nhiều)
            inst_ref = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INSTANCE-REFS/{NS_MAP_KEY}:SERVICE-INSTANCE-REF")
            mach_ref = self._get_text(elem, f".//{NS_MAP_KEY}:MACHINE-REF")
            
            if sn and path not in self.model.instance_to_machine_mappings and inst_ref and mach_ref:
                
                # FIX v1.3: Kiểm tra port ở 2 vị trí (trong endpoint hoặc con trực tiếp)
                tcp_port_str = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INSTANCE-ENDPOINT/{NS_MAP_KEY}:TCP-PORT")
                if not tcp_port_str:
                    tcp_port_str = self._get_text(elem, f"{NS_MAP_KEY}:TCP-PORT") # Kiểm tra con trực tiếp

                udp_port_str = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INSTANCE-ENDPOINT/{NS_MAP_KEY}:UDP-PORT")
                if not udp_port_str:
                    udp_port_str = self._get_text(elem, f"{NS_MAP_KEY}:UDP-PORT") # Kiểm tra con trực tiếp

                self.model.instance_to_machine_mappings[path] = ServiceInstanceToMachineMapping(
                    short_name=sn, ar_path=path, instance_ref=inst_ref, machine_ref=mach_ref,
                    tcp_port=int(tcp_port_str) if tcp_port_str is not None else None,
                    udp_port=int(udp_port_str) if udp_port_str is not None else None
                )

        # 7c. Instance-to-Port (Đã đúng)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:SERVICE-INSTANCE-TO-PORT-PROTOTYPE-MAPPING", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            inst_ref = self._get_text(elem, f".//{NS_MAP_KEY}:SERVICE-INSTANCE-REF")
            port_ref = self._get_text(elem, f".//{NS_MAP_KEY}:TARGET-PORT-PROTOTYPE-REF")
            
            if sn and path not in self.model.instance_to_port_mappings and inst_ref and port_ref:
                self.model.instance_to_port_mappings[path] = ServiceInstanceToPortMapping(
                    short_name=sn, ar_path=path, instance_ref=inst_ref, port_ref=port_ref
                )

        # 7d. Process Definitions (MỚI để kiểm tra Lỗi 7)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:PROCESS", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            if sn and path not in self.model.process_definitions:

                proc_def = ProcessDefinition(short_name=sn, ar_path=path)

                # Tìm các tham chiếu MachineState vi phạm R19-11
                ms_refs = elem.xpath(
                    f".//{NS_MAP_KEY}:STATE-DEPENDENT-STARTUP-CONFIGS"
                    f"//*/{NS_MAP_KEY}:CONTEXT-MODE-DECLARATION-GROUP-PROTOTYPE-REF",
                    namespaces=self._ns_map
                )

                for ref_elem in ms_refs:
                    ref_text = ref_elem.text
                    if ref_text and "MachineState" in ref_text:
                        proc_def.machine_state_references.append(ref_text)

                self.model.process_definitions[path] = proc_def

        # --- CÁC ĐỐI TƯỢNG TRUNG GIAN (v1.3) ---

        # 8. Network Endpoints (MỚI v1.3)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:NETWORK-ENDPOINT", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            if sn and path not in self.model.network_endpoints:
                ip_addr = self._get_text(elem, f".//{NS_MAP_KEY}:IPV-4-CONFIGURATION/{NS_MAP_KEY}:IPV-4-ADDRESS")
                netmask = self._get_text(elem, f".//{NS_MAP_KEY}:IPV-4-CONFIGURATION/{NS_MAP_KEY}:NETWORK-MASK")
                gateway = self._get_text(elem, f".//{NS_MAP_KEY}:IPV-4-CONFIGURATION/{NS_MAP_KEY}:DEFAULT-GATEWAY")
                
                self.model.network_endpoints[path] = NetworkEndpoint(
                    short_name=sn, ar_path=path, ip_address=ip_addr, netmask=netmask, gateway=gateway
                )
        
        # 9. Machine Designs (MỚI v1.3)
        for elem in root.xpath(f"//*/{NS_MAP_KEY}:MACHINE-DESIGN", namespaces=self._ns_map):
            sn = self._get_text(elem, f"{NS_MAP_KEY}:SHORT-NAME")
            path = self._get_ar_path(elem)
            if sn and path not in self.model.machine_designs:
                ep_ref = self._get_text(elem, f".//{NS_MAP_KEY}:UNICAST-NETWORK-ENDPOINT-REF")
                
                self.model.machine_designs[path] = MachineDesign(
                    short_name=sn, ar_path=path, network_endpoint_ref=ep_ref
                )