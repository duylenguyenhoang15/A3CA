# /a3ca_layer1/parser/xsd_validator.py
import sys
from pathlib import Path
from lxml import etree
from typing import Optional

_schema_cache: dict[Path, etree.XMLSchema] = {}

class XSDValidatorError(Exception):
    """Lỗi tùy chỉnh cho các vấn đề xác thực XSD."""
    pass

def _get_schema(xsd_path: Path) -> etree.XMLSchema:
    """Tải và parse XSD schema, sử dụng cache."""
    if xsd_path not in _schema_cache:
        try:
            # FIX: Vẫn cần resolve_entities để đọc xml.xsd,
            # nhưng không cần (và không nên) bật no_network=False nữa.
            xsd_parser = etree.XMLParser(
                resolve_entities=True
            )
            
            xsd_doc = etree.parse(str(xsd_path), xsd_parser)
            
            _schema_cache[xsd_path] = etree.XMLSchema(xsd_doc)
        except etree.XMLSchemaParseError as e:
            raise XSDValidatorError(f"Không thể parse XSD: {e}")
        except OSError as e:
            raise XSDValidatorError(f"Không thể đọc file XSD '{xsd_path}': {e}")
    return _schema_cache[xsd_path]

def validate_arxml(arxml_path: Path, xsd_path: Path) -> bool:
    """
    Xác thực một tệp ARXML dựa trên một tệp XSD.
    Ném ra lxml.etree.DocumentInvalid nếu không hợp lệ.
    """
    print(f"   [Validate] Đang xác thực '{arxml_path.name}'...", file=sys.stderr)
    try:
        schema = _get_schema(xsd_path)
        arxml_doc = etree.parse(str(arxml_path))
        
        schema.assertValid(arxml_doc) 
        
        print(f"   [Validate] SUCCESS: '{arxml_path.name}' hợp lệ.", file=sys.stderr)
        return True
    
    except etree.DocumentInvalid as e:
        print(f"   [Validate] FAILED: '{arxml_path.name}' không hợp lệ.\n{e}", file=sys.stderr)
        raise e
    
    except etree.XMLSyntaxError as e:
        print(f"   [Validate] FAILED: Lỗi cú pháp XML trong '{arxml_path.name}'.\n{e}", file=sys.stderr)
        raise XSDValidatorError(f"Lỗi cú pháp XML: {e}")
    
    except OSError as e:
        raise XSDValidatorError(f"Không thể đọc file ARXML '{arxml_path}': {e}")