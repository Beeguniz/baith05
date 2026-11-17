# Ingestion Service đến Giai đoạn 5

Service nhận JSON thật từ ESP32, kiểm tra dữ liệu, phát hiện bản tin trùng trong
SQLite và ghi log. Database được lưu cố định tại `data/greenhouse.db`.

## Cài đặt trên Windows 11

Từ thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Nếu PowerShell chặn activate script, có thể gọi Python trong venv trực tiếp:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Chạy

Đảm bảo Mosquitto và ESP32 đang hoạt động, sau đó:

```powershell
python .\ingest\ingest_service.py
```

Mặc định service kết nối `127.0.0.1:1883`, subscribe topic
`cse3069/th05/esp32/telemetry` với QoS 1.

Có thể đổi cấu hình bằng biến môi trường:

```powershell
$env:CSE3069_MQTT_HOST = '127.0.0.1'
$env:CSE3069_MQTT_PORT = '1883'
$env:CSE3069_MQTT_TOPIC = 'cse3069/th05/esp32/telemetry'
python .\ingest\ingest_service.py
```

Log hợp lệ có dạng:

```text
ACCEPTED quality=VALID device_id=esp32_dht11 ... temperature=29.3 humidity=98.0
```

Các trạng thái:

- `VALID`: bản đo hợp lệ.
- `INVALID_SENSOR`: ESP32 báo lỗi đọc với hai giá trị `null`.
- `SUSPECT`: giá trị ngoài dải kiểm tra nhưng vẫn được giữ nguyên.
- `REJECTED`: thiếu trường, sai kiểu hoặc logic `valid`/`null` không đúng.
- `DUPLICATE`: trùng khóa `device_id + boot_id + seq`, bị UNIQUE constraint
  trong SQLite từ chối.

Nhấn `Ctrl+C` để dừng. SQLite dùng WAL, `synchronous=FULL`, busy timeout 5 giây
và transaction cho từng bản ghi. Database không bị xóa khi service khởi động.

