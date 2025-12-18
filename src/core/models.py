"""
Telecom Package Models - Pydantic schemas for structured telecom data extraction.

This module defines the core data models for telecom package extraction:
- TelecomPackage: Main model for individual packages
- ExtractionResult: Wrapper for batch extraction results
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PackageAttributes(BaseModel):
    """
    Structured attributes for telecom packages.
    Matches PACKAGE_FIELDS schema for consistency.
    """
    nha_mang: Optional[str] = Field(default=None, alias="Nhà mạng", description="Tên nhà mạng cung cấp gói cước")
    thoi_gian_thanh_toan: Optional[str] = Field(default=None, alias="Thời gian thanh toán", description="Hình thức thanh toán: 'Trả trước' hoặc 'Trả sau'")
    cac_dich_vu_tien_quyet: Optional[str] = Field(default=None, alias="Các dịch vụ tiên quyết", description="Các dịch vụ cần có trước khi đăng ký gói")
    gia_vnd: Optional[int] = Field(default=None, alias="Giá (VNĐ)", description="Giá của gói cước trong một chu kỳ (VNĐ)")
    chu_ky_ngay: Optional[int] = Field(default=None, alias="Chu kỳ (ngày)", description="Thời gian hiệu lực của gói cước (ngày)")
    data_4g_tieu_chuan_ngay: Optional[str] = Field(default=None, alias="4G tốc độ tiêu chuẩn/ngày", description="Dung lượng 4G tốc độ tiêu chuẩn mỗi ngày")
    data_4g_cao_ngay: Optional[str] = Field(default=None, alias="4G tốc độ cao/ngày", description="Dung lượng 4G tốc độ cao mỗi ngày")
    data_4g_tieu_chuan_chu_ky: Optional[str] = Field(default=None, alias="4G tốc độ tiêu chuẩn/chu kỳ", description="Dung lượng 4G tốc độ tiêu chuẩn cho cả chu kỳ")
    data_4g_cao_chu_ky: Optional[str] = Field(default=None, alias="4G tốc độ cao/chu kỳ", description="Dung lượng 4G tốc độ cao cho cả chu kỳ")
    goi_noi_mang: Optional[str] = Field(default=None, alias="Gọi nội mạng", description="Chi tiết ưu đãi gọi nội mạng")
    goi_ngoai_mang: Optional[str] = Field(default=None, alias="Gọi ngoại mạng", description="Chi tiết ưu đãi gọi ngoại mạng")
    tin_nhan: Optional[str] = Field(default=None, alias="Tin nhắn", description="Chi tiết ưu đãi tin nhắn")
    chi_tiet: Optional[str] = Field(default=None, alias="Chi tiết", description="Mô tả thêm về gói cước")
    tu_dong_gia_han: Optional[str] = Field(default=None, alias="Tự động gia hạn", description="Có tự động gia hạn hay không: 'Có' hoặc 'Không'")
    cu_phap_dang_ky: Optional[str] = Field(default=None, alias="Cú pháp đăng ký", description="Hướng dẫn cú pháp SMS để đăng ký gói")
    
    class Config:
        populate_by_name = True


class TelecomPackageStrict(BaseModel):
    """
    Strict telecom package structure for Gemini structured output.
    Only contains service code (Mã dịch vụ) and attributes.
    """
    ma_dich_vu: str = Field(
        alias="Mã dịch vụ",
        description="Mã định danh duy nhất của gói cước (e.g., 'SD70', 'VIP', 'STANDARD')"
    )
    attributes: PackageAttributes = Field(
        default_factory=PackageAttributes,
        description="Package attributes containing all other fields"
    )
    
    class Config:
        populate_by_name = True


class TelecomPackage(BaseModel):
    """
    Telecommunication package structure for structured extraction.
    
    This model represents a single telecom package with dynamic attributes
    stored in a flexible dictionary structure to accommodate various
    package types (data, voice, TV, combo, etc.)
    """
    ma_dich_vu: str = Field(
        ...,
        alias="Mã dịch vụ",
        description="Name/code of the package (e.g., 'VIP', 'STANDARD', 'VSport', 'GALAXY')"
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="""Dynamic dictionary for variable package fields including:
        - price: Package price in VND
        - billing_cycle: Subscription period (e.g., '1 tháng', '6 tháng', '12 tháng')
        - payment_type: 'trả trước' (prepaid) or 'trả sau' (postpaid)
        - data_limit: Data allowance if applicable
        - channels: Number of TV channels if applicable
        - speed: Internet speed if applicable
        - promotion: Any promotional details
        - bonus_codes: Number of bonus/lottery codes if applicable
        - notes: Additional notes or special conditions
        """
    )
    
    @classmethod
    def from_strict(cls, strict_pkg: TelecomPackageStrict) -> "TelecomPackage":
        """Convert from strict schema to flexible schema."""
        attrs = strict_pkg.attributes.model_dump(exclude_none=True, by_alias=True)
        
        # Extract fields that were moved to attributes
        name = strict_pkg.ma_dich_vu
        
        return cls(
            ma_dich_vu=name,
            attributes=attrs
        )
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "ma_dich_vu": "VIP",
                "attributes": {
                    "price": 80000,
                    "billing_cycle": "1 tháng",
                    "payment_type": "trả trước",
                    "bonus_codes": 1
                }
            }
        }


class ExtractionResult(BaseModel):
    """
    Container for batch extraction results.
    
    Wraps multiple TelecomPackage objects with extraction metadata.
    """
    packages: List[TelecomPackage] = Field(
        default_factory=list,
        description="List of extracted telecom packages"
    )
    source_document: Optional[str] = Field(
        default=None,
        description="Source document name or path"
    )
    extraction_date: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of extraction"
    )
    total_count: int = Field(
        default=0,
        description="Total number of packages extracted"
    )
    
    def model_post_init(self, __context):
        """Update total_count after initialization."""
        object.__setattr__(self, 'total_count', len(self.packages))
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert packages to list of dictionaries for JSON serialization."""
        return [pkg.model_dump() for pkg in self.packages]


# For LangChain structured output - wrapper to handle multiple packages
class PackageListOutputStrict(BaseModel):
    """LangChain-compatible output schema with strict types for OpenAI structured output."""
    packages: List[TelecomPackageStrict] = Field(
        description="List of extracted telecom packages from the document"
    )


class PackageListOutput(BaseModel):
    """LangChain-compatible output schema for multiple packages."""
    packages: List[TelecomPackage] = Field(
        description="List of extracted telecom packages from the document"
    )
