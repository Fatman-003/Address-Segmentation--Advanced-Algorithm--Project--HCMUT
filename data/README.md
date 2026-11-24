# Development Address Dictionary (`data/`)

Thư mục này chứa **bộ từ điển địa danh phát triển (development reference dataset)** theo đúng quy ước đầu ra chuẩn của mẫu dữ liệu: các giá trị `province`, `ward`, `street` là **tên chuẩn không kèm tiền tố hành chính** (`Tỉnh`, `Thành phố`, `Phường`, `Xã`, `Đường`, `Phố`, `Ngõ`, `Hẻm`, `Ngách`...).

> **Lưu ý theo `contract.md`:** Không hard-code dữ liệu này vào thuật toán và không giả định có quan hệ phân cấp `street -> ward -> province`. Khi giảng viên cung cấp file chính thức, toàn bộ giá trị đầu ra chuẩn sẽ lấy trực tiếp từ dữ liệu mới được nạp.

## Cấu trúc các file hiện có

| File | Mục đích | Định dạng |
| --- | --- | --- |
| `provinces.txt` | Danh sách 64 tên Tỉnh / Thành phố (bao gồm đầy đủ 34 đơn vị sau sáp nhập 2025 và toàn bộ 63 tỉnh/thành cũ, dạng tên chuẩn không tiền tố) | UTF-8, mỗi dòng 1 tên chuẩn |
| `wards.txt` | Danh sách Phường / Xã mẫu không tiền tố (gồm phường/xã mới từ bảng mẫu và các phường cũ tại TP.HCM, Hà Nội, Hải Phòng, Đà Nẵng, Huế, Cần Thơ, Nha Trang, Quy Nhơn, Đồng Hới, Vinh) | UTF-8, mỗi dòng 1 tên chuẩn |
| `streets.txt` | Danh sách tên đường mẫu không tiền tố (vd: `An Dương`, `Tây 4`, `C1`, `Cách Mạng Tháng 8`, `Lộ Triền Đồng`, `3/2`) | UTF-8, mỗi dòng 1 tên chuẩn |
| `prefixes.json` | Quy tắc tiền tố hành chính (`Thành phố`, `Tỉnh`, `Phường`, `Xã`, `Đường`, `Phố`), tiền tố ngõ/hẻm/ngách và bảng mở rộng viết tắt | JSON |
| `aliases.json` | Bảng alias/viết tắt phổ biến (`HCM`, `TPHCM`, `BRVT`, `TTH`, `CMT8`, `QL1A`, `3 thang 2`...) | JSON ánh xạ `canonical -> [aliases]` |

## Khả năng tương thích khi giảng viên đổi schema

Module `src/searching/dictionary.py` (`AddressDictionary.from_directory`) hỗ trợ tự động đọc cả file tách lớp (`.txt`, `.csv`, `.json`, `.jsonl`) lẫn file bảng gộp dạng `ID,text,province,ward,street` (`.csv`, `.json`, `.jsonl`). Các alias trong `aliases.json` chỉ được kích hoạt nếu tên chuẩn đích tồn tại trong dữ liệu đang nạp.
