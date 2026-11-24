# Address Segmentation Module

Module phân tách chuỗi địa chỉ thô (bao gồm dữ liệu nhiễu từ OCR) thành các thành phần hành chính cơ bản: **Street** (Đường/Số nhà), **Ward** (Phường/Xã/Thị trấn), và **Province** (Tỉnh/Thành phố).

Module được viết hoàn toàn bằng Python thuần (chỉ sử dụng thư viện chuẩn `re`), không phụ thuộc thư viện bên ngoài.

## 1. Quy trình xử lý (Pipeline)

Mỗi chuỗi đầu vào đi qua 5 bước tuần tự trong hàm `segment_address()`:

1. **Kiểm tra rỗng:** Trả về danh sách `spans` rỗng nếu chuỗi đầu vào là `None`, rỗng hoặc chỉ chứa khoảng trắng.
2. **Bỏ dấu tiếng Việt (`remove_accents`):** Chuyển toàn bộ ký tự có dấu sang không dấu bằng bảng ánh xạ `str.maketrans` để đồng bộ hóa đầu vào cho bộ lọc.
3. **Dọn dẹp nhiễu OCR (`clean_ocr_text`):**
   * Xóa ký tự rác rìa ảnh: `|`, `[`, `]`, `{`, `}`, `_`, `~`.
   * Tách dấu chấm dính chữ (`P.Ben` $\rightarrow$ `P. Ben`).
   * Tách tiền tố dính số (`P12` $\rightarrow$ `P 12`, `F4` $\rightarrow$ `F 4`).
   * Tách chữ dính sau số nhà có dấu gạch chéo (`3/2p.14` $\rightarrow$ `3/2 p. 14`).
   * Chuẩn hóa khoảng trắng thừa.
4. **Chuẩn hóa hướng địa chỉ (`handle_address_direction`):** Phát hiện địa chỉ viết ngược (Tỉnh/TP đứng đầu, có dấu phẩy) và tự động đảo ngược về hướng xuôi chuẩn (`Đường, Phường, Tỉnh`).
5. **Phân tách lõi:**
   * **Có dấu phẩy (`_split_by_comma`):** Cắt theo vị trí phần tử.
   * **Không có dấu phẩy (`_split_freeform`):** Tìm vị trí các từ khóa neo (`WARD_ANCHORS`, `PROVINCE_ANCHORS`). Nếu thiếu neo, dùng cơ chế dự phòng cắt 2-gram từ cuối chuỗi lên.

---

## 2. Các trường hợp được hỗ trợ

| Trường hợp | Ví dụ đầu vào (`raw_address`) | Kết quả phân tách (`spans`) |
| :--- | :--- | :--- |
| **Địa chỉ chuẩn (3+ phần có dấu phẩy)** | `123 Lê Lợi, Phường Bến Nghé, TP. Hồ Chí Minh` | `street`: `123 Le Loi`<br>`ward`: `Phuong Ben Nghe`<br>`province`: `TP. Ho Chi Minh` |
| **Địa chỉ 2 phần (có dấu phẩy)** | `12 Trần Hưng Đạo, Hà Nội` | `street`: `12 Tran Hung Dao`<br>`province`: `Ha Noi` |
| **Nhiễu OCR (rác, dính chữ/số)** | `\|3/2p.14\|, P.Ben Nghe, TP.HCM` | `street`: `3/2 p. 14`<br>`ward`: `P. Ben Nghe`<br>`province`: `TP. HCM` |
| **Địa chỉ viết ngược** | `TP. Hồ Chí Minh, Phường 12, 456 CMT8` | `street`: `456 CMT8`<br>`ward`: `Phuong 12`<br>`province`: `TP. Ho Chi Minh` |
| **Viết liền không dấu phẩy (có Anchor)** | `45 Nguyễn Huệ Phường Bến Nghé TP. HCM` | `street`: `45 Nguyen Hue`<br>`ward`: `Phuong Ben Nghe`<br>`province`: `TP. HCM` |
| **Viết liền, không Anchor (Fallback n-gram)** | `10 Hai Ba Trung Da Nang` | `street`: `10 Hai`<br>`ward`: `Ba Trung`<br>`province`: `Da Nang` |
| **Chuỗi quá ngắn (< 4 từ, không dấu phẩy)** | `123 Lê Lợi` | `street`: `123 Le Loi` |
| **Chuỗi rỗng / khoảng trắng** | `"   "` | `[]` |

---

## 3. Cách sử dụng (API Contract)

### Chữ ký hàm
```python
segment_address(raw_address: str) -> dict