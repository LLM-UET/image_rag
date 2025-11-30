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
    Uses explicit fields instead of Dict[str, Any] for OpenAI structured output compatibility.
    """
    price: Optional[int] = Field(default=None, description="Package price in VND")
    billing_cycle: Optional[str] = Field(default=None, description="Subscription period (e.g., '1 tháng', '6 tháng')")
    payment_type: Optional[str] = Field(default=None, description="'prepaid'/'trả trước' or 'postpaid'/'trả sau'")
    data_limit: Optional[str] = Field(default=None, description="Data allowance if applicable")
    channels: Optional[int] = Field(default=None, description="Number of TV channels if applicable")
    speed: Optional[str] = Field(default=None, description="Internet speed if applicable")
    promotion: Optional[str] = Field(default=None, description="Any promotional details")
    bonus_codes: Optional[int] = Field(default=None, description="Number of bonus/lottery codes if applicable")
    notes: Optional[str] = Field(default=None, description="Additional notes or special conditions")
    voice_minutes: Optional[str] = Field(default=None, description="Voice call minutes if applicable")
    sms_count: Optional[int] = Field(default=None, description="SMS count if applicable")


class TelecomPackageStrict(BaseModel):
    """
    Strict telecom package structure for OpenAI structured output.
    Uses PackageAttributes instead of Dict for schema compatibility.
    """
    name: str = Field(
        description="Name/code of the package (e.g., 'VIP', 'STANDARD', 'VSport', 'GALAXY')"
    )
    partner_name: str = Field(
        description="Telecom partner or service provider (e.g., 'TV360', 'VNPT', 'Viettel', 'Mobifone')"
    )
    service_type: str = Field(
        description="Type of service (e.g., 'Television', 'Internet', 'Mobile', 'Combo', 'Camera')"
    )
    attributes: PackageAttributes = Field(
        default_factory=PackageAttributes,
        description="Package attributes like price, billing cycle, etc."
    )


class TelecomPackage(BaseModel):
    """
    Telecommunication package structure for structured extraction.
    
    This model represents a single telecom package with dynamic attributes
    stored in a flexible dictionary structure to accommodate various
    package types (data, voice, TV, combo, etc.)
    """
    name: str = Field(
        description="Name/code of the package (e.g., 'VIP', 'STANDARD', 'VSport', 'GALAXY')"
    )
    partner_name: str = Field(
        description="Telecom partner or service provider (e.g., 'TV360', 'VNPT', 'Viettel', 'Mobifone')"
    )
    service_type: str = Field(
        description="Type of service (e.g., 'Television', 'Internet', 'Mobile', 'Combo', 'Camera')"
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
        attrs = strict_pkg.attributes.model_dump(exclude_none=True)
        return cls(
            name=strict_pkg.name,
            partner_name=strict_pkg.partner_name,
            service_type=strict_pkg.service_type,
            attributes=attrs
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "VIP",
                "partner_name": "TV360",
                "service_type": "Television",
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
