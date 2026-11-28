import re

#==== chuyen sang khong dau === 
"""_ACCENT_GROUPS = {
    "a": "áàảãạăắằẳẵặâấầẩẫậ",
    "e": "éèẻẽẹêếềểễệ",
    "i": "íìỉĩị",
    "o": "óòỏõọôốồổỗộơớờởỡợ",
    "u": "úùủũụưứừửữự",
    "y": "ýỳỷỹỵ",
    "d": "đ",
}

_ACCENT_TRANS_TABLE = str.maketrans(
    {
        char: base
        for base, chars in _ACCENT_GROUPS.items()
        for char in chars
    }
    | {
        char.upper(): base.upper()
        for base, chars in _ACCENT_GROUPS.items()
        for char in chars
    }
)


def remove_accents(text: str) -> str:
    if not text:
        return ""
    return text.translate(_ACCENT_TRANS_TABLE)
"""
# ==============================================================================
# 1. BỘ REGEX TỐI ƯU HÓA HIỆU NĂNG (PRE-COMPILED REGEX)
# ==============================================================================

# Regex phát hiện hướng viết ngược (Tỉnh/Thành phố đứng ở đầu chuỗi)
REVERSE_DETECTION_RE = re.compile(
    r"^(thanh\s+pho|tp\.?|tinh|t\.|ho\s+chi\s+minh|hcm|ha\s+noi|hn|da\s+nang|dn|hai\s+phong|can\s+tho)\b",
    re.IGNORECASE
)

DOT_SPLITTER_RE = re.compile(r"([a-z]+)\.(?=[a-z0-9])", re.IGNORECASE)
PREFIX_NUMBER_SPLITTER_RE = re.compile(r"\b(p|q|f|h|tx|d)(\d+)\b", re.IGNORECASE)
SLASH_WORD_SPLITTER_RE = re.compile(r"(\d+/\d+)([a-z]+)", re.IGNORECASE)

_BOUNDARY = r"(?![a-zà-ỹ0-9_])"

PROVINCE_ANCHORS = re.compile(
    rf"(?:thành\s+phố|tp\.?|tỉnh|t\.|hồ\s+chí\s+minh|hcm|hà\s+nội|hn|đà\s+nẵng|đn|hải\s+phòng|cần\s+thơ){_BOUNDARY}",
    re.IGNORECASE,
)

WARD_ANCHORS = re.compile(
    rf"(?:phường|p\.?|xã|x\.?|thị\s+trấn|tt\.?|f\.?){_BOUNDARY}",
    re.IGNORECASE,
)

STREET_ANCHORS = re.compile(
    rf"(?:đường|đ\.?|phố|đại\s+lộ|đl|ngõ|ngách|hẻm|kiệt){_BOUNDARY}",
    re.IGNORECASE,
)

STREET_PREFIX_RE = re.compile(
    rf"^(?:ngách|ngõ|hẻm|đường|phố|đại\s+lộ|lộ|kiệt|số){_BOUNDARY}"
    r"(?:\s+\d+(?:/\d+)*[a-zà-ỹ]*)?\s*",
    re.IGNORECASE,
)

# ==============================================================================
# 2. CÁC HÀM TIỀN XỬ LÝ VÀ DỌN DẸP CHUỖI (PREPROCESSING)
# ==============================================================================

def clean_ocr_text(text: str) -> str:
    if not text:
        return ""
    
    # Loại bỏ ký tự rác OCR rìa ảnh
    text = re.sub(r"[|\[\]{}_~]", " ", text)
    
    # Tách dấu chấm dính chữ (Ví dụ: "P.Ben" -> "P. Ben")
    text = DOT_SPLITTER_RE.sub(r"\1. ", text)
    
    # Tách tiền tố dính số (Ví dụ: "P12" -> "P 12", "F4" -> "F 4")
    text = PREFIX_NUMBER_SPLITTER_RE.sub(r"\1 \2", text)
    
    # Tách chữ dính sau xuyệt số nhà (Ví dụ: "3/2p.14" -> "3/2 p.14")
    text = SLASH_WORD_SPLITTER_RE.sub(r"\1 \2", text)
    
    # Chuẩn hóa khoảng trắng
    return " ".join(text.split())


def handle_address_direction(text: str) -> str:
    if not text:
        return ""
    
    # Kiểm tra xem chuỗi có bắt đầu bằng Tỉnh/TP không
    if REVERSE_DETECTION_RE.match(text):
        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip()]
            parts.reverse()  # Đảo ngược: [Tỉnh, Phường, Đường] -> [Đường, Phường, Tỉnh]
            return ", ".join(parts)
            
    return text

# ==============================================================================
# 3. THUẬT TOÁN PHÂN TÁCH LÕI (CORE SEGMENTATION ENGINE)
# ==============================================================================

def extract_after_street_prefix(street: str | None) -> str | None:
    """
    Nếu street bắt đầu bằng tiền tố trong danh sách (ngách, ngõ, hẻm, đường, phố, đại lộ, lộ, kiệt, số),
    tìm từ khóa đường/phố phía sau và trả về phần nằm sau từ khóa đó.
    """
    if not street:
        return street

    s = street.strip()
    prefix_match = STREET_PREFIX_RE.match(s)
    if not prefix_match:
        return s

    # Tìm từ khóa đường/phố bắt đầu từ sau cụm tiền tố đầu chuỗi
    search_start = prefix_match.end()
    anchor_match = STREET_ANCHORS.search(s, pos=search_start)
    if not anchor_match:
        return s

    cleaned = s[anchor_match.end():].strip(" ,.-")
    return cleaned or s

def _split_by_comma(text: str) -> tuple[str | None, str | None, str | None]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    street = None
    ward = None
    province = None
    
    # Ánh xạ theo vị trí (sau khi đã được đảm bảo ở hướng xuôi bằng handle_address_direction)
    if len(parts) >= 3:
        street = parts[0]
        ward = parts[1]
        province = parts[-1]
    elif len(parts) == 2:
        street = parts[0]
        province = parts[1]
    elif len(parts) == 1:
        return _split_freeform(parts[0])
        
    return street, ward, province


def _split_freeform(text: str) -> tuple[str | None, str | None, str | None]:
    street = None
    ward = None
    province = None
    
    # Tìm vị trí xuất hiện của các neo hành chính
    prov_matches = list(PROVINCE_ANCHORS.finditer(text))
    ward_matches = list(WARD_ANCHORS.finditer(text))
    
    if ward_matches and prov_matches:
        w_idx = ward_matches[0].start()
        p_idx = prov_matches[0].start()
        
        if w_idx < p_idx:
            street = text[:w_idx].strip()
            ward = text[w_idx:p_idx].strip()
            province = text[p_idx:].strip()
            return street, ward, province
            
    # Trường hợp dự phòng nếu thiếu neo: Cắt cứng bằng n-gram từ đuôi lên
    tokens = text.split()
    n = len(tokens)
    
    if n >= 4:
        province = " ".join(tokens[-2:])
        ward = " ".join(tokens[-4:-2])
        street = " ".join(tokens[:-4])
    else:
        # Nếu chuỗi quá ngắn, đưa hết về trường street để Thành viên 4 xử lý fuzzy
        street = text
        
    return street, ward, province


def strip_street_prefix(street: str | None) -> str | None:
    """Loại bỏ tiền tố loại đường/ngõ/hẻm và số đứng đầu để giữ tên đường."""
    if not street:
        return street
    cleaned = STREET_PREFIX_RE.sub("", street.strip()).strip()
    return cleaned or street.strip()

# ==============================================================================
# 4. CHỮ KÝ API BẮT BUỘC THEO HỢP ĐỒNG (CONTRACT API)
# ==============================================================================

def segment_address(raw_address: str) -> dict:
    """
    Hàm phân tách địa chỉ chính thức của Thành viên 2.
    Đầu vào: Chuỗi địa chỉ thô từ OCR.
    Đầu ra: Dict chứa các spans đã phân đoạn (Street, Ward, Province).
    """

    
    if not raw_address or not raw_address.strip():
        return {"raw_address": raw_address, "spans": []}
    
    # Bước 1: Chuẩn hóa sang không dấu
   # no_accent = remove_accents(raw_address)
    
    # Bước 2: Dọn dẹp OCR (truyền no_accent thay vì raw_address)
    cleaned = clean_ocr_text(raw_address)
    
    # Bước 3: Nhận diện hướng viết ngược và đưa về dạng xuôi chuẩn
    normalized_direction = handle_address_direction(cleaned)
    
    # Bước 3: Phân tách ra 3 phần tử (Tuplet)
    if "," in normalized_direction:
        street_cand, ward_cand, province_cand = _split_by_comma(normalized_direction)
    else:
        street_cand, ward_cand, province_cand = _split_freeform(normalized_direction)
    
    # Bước 4: Đóng gói dữ liệu ra đúng cấu trúc Spans của Contract JSON
    spans = []
    street_final = extract_after_street_prefix(street_cand)
    if street_cand:
        spans.append({"field": "street", "text": street_final})
    if ward_cand:
        spans.append({"field": "ward", "text": ward_cand})
    if province_cand:
        spans.append({"field": "province", "text": province_cand})
        
    return {
        "raw_address": raw_address,
        "spans": spans
    }