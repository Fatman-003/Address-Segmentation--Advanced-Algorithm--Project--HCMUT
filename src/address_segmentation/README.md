# Address Segmentation Module

Module phân tách chuỗi địa chỉ thô (bao gồm dữ liệu nhiễu từ OCR) thành các thành phần hành chính cơ bản: **Street** (Đường/Số nhà), **Ward** (Phường/Xã/Thị trấn), và **Province** (Tỉnh/Thành phố).

Module được viết hoàn toàn bằng Python thuần (chỉ sử dụng thư viện chuẩn `re`), không phụ thuộc thư viện bên ngoài.

Flow chart 
```mermaid
flowchart TD
    classDef io fill:#e0f2fe,stroke:#0284c7,stroke-width:1.5px,color:#0f172a
    classDef diamond fill:#fef9c3,stroke:#ca8a04,stroke-width:1.5px,color:#0f172a
    classDef proc fill:#f1f5f9,stroke:#475569,stroke-width:1.5px,color:#0f172a
    classDef fallback fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#0f172a

    P(["Start"]):::io --> A["Input: raw_address (str)"]:::io
    A --> B{"Rỗng hoặc<br/>chỉ có khoảng trắng?"}:::diamond
    B -- "True" --> C["Trả về spans: []"]:::io
    B -- "False" --> D["clean_ocr_text()<br/>Xóa ký tự rác, tách dấu chấm/số/gạch chéo,<br/>chuẩn hóa khoảng trắng"]:::proc

    D --> E["handle_address_direction()<br/>Bắt đầu bằng Tỉnh/TP và có dấu phẩy<br/>thì đảo ngược thứ tự"]:::proc

    E --> F{"bypass_comma()<br/>Bắt đầu bằng<br/>ngõ/ngách/hẻm?"}:::diamond
    F -- "True" --> G{"_split_freeform()<br/>Cắt theo WARD &<br/>PROVINCE ANCHORS?"}:::diamond
    F -- "False" --> H{"Có dấu phẩy ','?"}:::diamond

    H -- "True" --> I["_split_by_comma()<br/>Ánh xạ theo vị trí: street, ward, province"]:::proc
    H -- "False" --> G

    I --> J["extract_after_street_prefix()<br/>Nếu bắt đầu bằng tiền tố đường/ngõ/hẻm/số<br/>và có anchor đường/phố sau thì lấy phần sau"]:::proc
    G -- "True" --> J
    G -- "False" --> M["Fallback n-gram từ cuối"]:::fallback
    M --> J

    J --> K["Đóng gói spans [{'field': ..., 'text': ...}]"]:::proc
    K --> L["Output: {'raw_address': raw_address, 'spans': spans}"]:::io
    L --> O(["End"]):::io
   ```

    hàm cần call back: 
    def segment_address(raw_address: str) -> dict:

    input: raw_address: str
    output: spans bao gồm 3 trường street, ward, province
    example:
    {
  "raw_address": "Ngõ 97 Đường Gia Thượng, Phường Việt Hưng, Hà Nội",
  "spans": [
    { "field": "street", "text": "Gia Thượng" },
    { "field": "ward", "text": "Phường Việt Hưng" },
    { "field": "province", "text": "Hà Nội" }
  ]
}

   Các thay đổi: 
   - Hảm trả về có dấu
   - Có tách các từ khóa ngõ, ngách -> chỉ trả về đường
   - Các cụm từ khi được trả sẽ không bao gồm prefix 
   
   Risk assessments: 
   - Ví các anchor là tiếng viết có dấu nên có rất nhiều biến thể sai chính tả vì dấu mà trong đoạn code không cover hết được
   