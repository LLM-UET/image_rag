"""
Telecom Package Extractor - LangChain-based extraction pipeline.

This module provides:
- Specialized prompts for Vietnamese telecom document extraction
- LangChain chain with structured output (Pydantic)
- Extract function for processing cleaned text
"""
import json
import logging
from typing import List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from .models import (
    TelecomPackage, 
    TelecomPackageStrict, 
    PackageListOutput, 
    PackageListOutputStrict
)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

SYSTEM_PROMPT = """Bạn là một chuyên gia nhập liệu dữ liệu đang đọc các tài liệu hợp đồng và bảng giá viễn thông Việt Nam.

NHIỆM VỤ: Trích xuất TẤT CẢ các gói cước từ tài liệu và chuyển đổi thành định dạng cấu trúc JSON.

QUY TẮC XỬ LÝ DỮ LIỆU LỖI / OCR KÉM (ƯU TIÊN CAO NHẤT):
1. PHÁT HIỆN DỮ LIỆU RÁC: Nếu thấy văn bản chính có dấu hiệu lặp lại vô nghĩa (ví dụ: một dòng lặp lại nội dung giống hệt nhau nhiều lần như "80 20,5... 80 20,5..."), HÃY BỎ QUA dòng văn bản đó.
2. TÌM KIẾM THAY THẾ: Ngay lập tức tìm kiếm dữ liệu trong phần "IMAGE DESCRIPTION" (Mô tả ảnh) hoặc "EXTRACTED CONTENT FROM IMAGES" thường nằm ở cuối trang hoặc cuối tài liệu.
3. ƯU TIÊN NGUỒN DỮ LIỆU: Dữ liệu bảng trong phần Mô tả ảnh luôn được coi là chính xác hơn văn bản chính bị lỗi định dạng.
4. RÀ SOÁT PHỤ LỤC: Đặc biệt chú ý các mục "Phụ lục" (Appendix). Các gói cước như Fiber50+, Fiber60+... thường nằm ở đây và hay bị lỗi OCR ở văn bản chính.

QUY TẮC XÁC ĐỊNH PARTNER_NAME (Tên đối tác/nhà cung cấp):
1. KIỂM TRA HEADER TRƯỚC: 
   - Tên đối tác thường xuất hiện ở tiêu đề tài liệu, logo, hoặc dòng đầu tiên
   - Ví dụ: "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" có thể kèm theo logo VNPT, Viettel, Mobifone
   - Hoặc trong tiêu đề như "Danh sách gói cước dịch vụ TV360" → partner_name = "TV360"
2. KIỂM TRA TRONG BẢNG:
   - Nếu không tìm thấy ở header, partner_name có thể nằm trong cột của bảng
   - Hoặc tên gói cước có tiền tố cho biết đối tác (VD: "VNPT_Data", "Viettel_V120")

QUY TẮC XÁC ĐỊNH SERVICE_TYPE (Loại dịch vụ):
   - Television/Truyền hình: TV360, K+, HBO GO, VTVcab
   - Internet: FiberVNN, MyTV, FTTH, FiberEco, FiberVIP...
   - Mobile/Di động: Data packages, Voice packages, Sim trả sau
   - Combo: Kết hợp nhiều dịch vụ

QUY TẮC MAPPING CỘT BẢNG → ATTRIBUTES:
| Tên cột tiếng Việt | Tên field trong attributes |
|-------------------|---------------------------|
| Đơn giá / Giá / Cước phí | giá |
| Chu kỳ gói cước / Thời hạn | thời hạn |
| Lưu lượng / Data | data |

QUY TẮC CHUẨN HÓA DỮ LIỆU:
1. giá: Chuyển thành số nguyên (VND), bỏ dấu chấm/phẩy ngăn cách hàng nghìn. Lấy giá trị cho 1 tháng nếu có nhiều cột giá.
   - "80.000" → 80000
   - "1.570.000" → 1570000
2.thời hạn: Giữ nguyên định dạng tiếng Việt ("1 tháng", "6 tháng"...).
3.phương thức trả: Xác định từ ngữ cảnh ("prepaid" hoặc "postpaid").
4. Xử lý nhiều cột giá: Nếu bảng có cột "Giá 1 tháng", "Giá 7 tháng", "Giá 15 tháng" -> Tạo bản ghi cho gói cước cơ bản (1 tháng). Nếu cần thiết mới tạo thêm gói chu kỳ dài.

OUTPUT FORMAT:
Trả về một đối tượng JSON có khóa `packages` (mảng). Mỗi mục trong `packages` là một object với các trường chính:

- `mã dịch vụ`: tên/mã gói (string)
- `attributes`: object chứa các thuộc tính linh hoạt (ví dụ: Thời gian thanh toán: Thường có hai giá trị "Trả trước" hoặc "Trả sau".
- Các dịch vụ tiên quyết: Các dịch vụ cần có trước khi đăng ký gói cước này, có thể để trống.
- Giá (VNĐ): Giá của gói cước trong một chu kỳ, tính theo đồng Việt Nam.
- Chu kỳ (ngày): Thời gian hiệu lực của gói cước tính theo ngày. Hết chu kỳ sẽ phải gia hạn để tiếp tục sử dụng.
- 4G tốc độ tiêu chuẩn/ngày: Dung lượng dữ liệu 4G tốc độ tiêu chuẩn mà người dùng nhận được mỗi ngày, được biểu hiện bằng số GB. Nếu sử dụng hết sẽ bị giảm tốc độ.
- 4G tốc độ cao/ngày
- 4G tốc độ tiêu chuẩn/chu kỳ
- 4G tốc độ cao/chu kỳ
- Gọi nội mạng: Chi tiết ưu đãi gọi nội mạng trong chu kỳ, ví dụ "Miễn phí 30 phút gọi"
- Gọi ngoại mạng
- Tin nhắn: Chi tiết ưu đãi tin nhắn trong chu kỳ.
- Chi tiết: Mô tả thêm về gói cước, bao gồm các ưu đãi, điều kiện sử dụng, giới hạn...
- Tự động gia hạn: Cho biết gói cước có tự động gia hạn sau khi hết chu kỳ hay không. Nhận giá trị "Có" hoặc "Không".
- Cú pháp đăng ký: Hướng dẫn cú pháp SMS hoặc thao tác để đăng ký gói cước.).

Không bao gồm các trường rỗng hoặc không tìm thấy trong `attributes`. Trả về CHỈ JSON (không có giải thích, không có markdown code block).

LƯU Ý QUAN TRỌNG:
- Trích xuất TẤT CẢ các gói, bao gồm cả các gói trong Phụ lục và Mô tả ảnh.
- Không bịa đặt dữ liệu nếu không tìm thấy.
- Trả về ONLY JSON,không có giải thích hay markdown code block"""


HUMAN_PROMPT = """Phân tích tài liệu sau và trích xuất tất cả các gói cước viễn thông:

{content}

Trả về kết quả dưới dạng JSON theo định dạng đã hướng dẫn."""


# ============================================================================
# EXTRACTION CHAIN
# ============================================================================

class TelecomPackageExtractor:
    """
    LangChain-based extractor for telecom packages.
    Uses structured output to enforce Pydantic schema.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp", use_strict_schema: bool = True):
        """
        Initialize the extractor with specified model.
        
        Args:
            model_name: Gemini model name (default: gemini-2.0-flash-exp)
            use_strict_schema: Use strict schema for structured output (default: True)
        """
        self.model_name = model_name
        self.use_strict_schema = use_strict_schema
        
        # Initialize LLM with structured output
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,  # Deterministic output for extraction
            google_api_key=settings.gemini_api_key
        )
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT)
        ])
        
        # Create chain with structured output - use strict schema for Gemini compatibility
        output_schema = PackageListOutputStrict if use_strict_schema else PackageListOutput
        self.structured_llm = self.llm.with_structured_output(output_schema)
        
        # Full chain
        self.chain = self.prompt | self.structured_llm
        
        logger.info(f"TelecomPackageExtractor initialized with model: {model_name}, strict_schema: {use_strict_schema}")
    
    def extract_package_info(self, clean_text: str) -> List[TelecomPackage]:
        """
        Extract telecom packages from cleaned text.
        
        Args:
            clean_text: Cleaned markdown text from clean_upstage_json()
            
        Returns:
            List of TelecomPackage objects
        """
        if not clean_text or not clean_text.strip():
            logger.warning("Empty text provided for extraction")
            return []
        
        try:
            logger.info(f"Extracting packages from text ({len(clean_text)} chars)")
            
            # Invoke chain with structured output
            result = self.chain.invoke({"content": clean_text})
            
            if result and result.packages:
                # Convert from strict schema to flexible schema if needed
                if self.use_strict_schema:
                    packages = [TelecomPackage.from_strict(pkg) for pkg in result.packages]
                else:
                    packages = result.packages
                
                logger.info(f"Successfully extracted {len(packages)} packages")
                return packages
            
            return []
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            # Fallback to manual JSON parsing
            return self._fallback_extraction(clean_text)
    
    def _fallback_extraction(self, clean_text: str) -> List[TelecomPackage]:
        """
        Fallback extraction without structured output (for error recovery).
        
        Args:
            clean_text: Text to extract from
            
        Returns:
            List of TelecomPackage objects
        """
        try:
            logger.info("Attempting fallback extraction...")
            
            response = self.llm.invoke([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": HUMAN_PROMPT.format(content=clean_text)}
            ])
            
            # Parse JSON from response
            content = response.content
            
            # Try to extract JSON
            json_data = self._parse_json_response(content)
            
            if json_data and 'packages' in json_data:
                packages = []
                for pkg_data in json_data['packages']:
                    try:
                        pkg = TelecomPackage(**pkg_data)
                        packages.append(pkg)
                    except Exception as e:
                        logger.warning(f"Failed to parse package: {e}")
                
                logger.info(f"Fallback extracted {len(packages)} packages")
                return packages
            
            return []
            
        except Exception as e:
            logger.error(f"Fallback extraction also failed: {e}")
            return []
    
    def _parse_json_response(self, text: str) -> Optional[dict]:
        """
        Parse JSON from LLM response with multiple strategies.
        
        Args:
            text: Raw LLM response text
            
        Returns:
            Parsed dictionary or None
        """
        # Try direct parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try extracting from code block
        import re
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except:
                pass
        
        # Try extracting between first { and last }
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end+1])
        except:
            pass
        
        return None


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def extract_package_info(clean_text: str, model_name: str = "gemini-2.0-flash-exp") -> List[TelecomPackage]:
    """
    Convenience function to extract packages from text.
    
    Args:
        clean_text: Cleaned markdown text
        model_name: LLM model to use
        
    Returns:
        List of TelecomPackage objects
    """
    extractor = TelecomPackageExtractor(model_name=model_name)
    return extractor.extract_package_info(clean_text)


if __name__ == "__main__":
    # Test extraction
    sample_text = """
    # Danh sách gói cước dịch vụ TV360
    
    | TT | Gói cước | Chu kỳ gói cước | Đơn giá | Ghi chú |
    |----|----------|-----------------|---------|---------|
    | I  | Gói cước trả trước |                 |         |         |
    | 1  | VIP      | 1 tháng         | 80.000  |         |
    | 2  | VIP      | 3 tháng         | 220.000 |         |
    | 3  | STANDARD | 1 tháng         | 50.000  |         |
    """
    
    packages = extract_package_info(sample_text)
    
    print("=" * 60)
    print(f"EXTRACTED {len(packages)} PACKAGES")
    print("=" * 60)
    
    for i, pkg in enumerate(packages, 1):
        print(f"\n{i}. {pkg.name} ({pkg.partner_name})")
        print(f"   Service: {pkg.service_type}")
        print(f"   Attributes: {json.dumps(pkg.attributes, ensure_ascii=False, indent=6)}")
