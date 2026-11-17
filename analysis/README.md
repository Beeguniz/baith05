# Truy vấn dữ liệu - Giai đoạn 5

Truy vấn dữ liệu một giờ gần nhất:

```powershell
.\.venv\Scripts\python.exe .\analysis\query_timerange.py `
  --device-id esp32_dht11
```

Truy vấn khoảng thời gian cụ thể và xuất CSV:

```powershell
.\.venv\Scripts\python.exe .\analysis\query_timerange.py `
  --device-id esp32_dht11 `
  --start '2026-11-17T11:50:00+07:00' `
  --end '2026-11-17T12:00:00+07:00' `
  --csv .\results\telemetry_export.csv
```

Thời gian phải có múi giờ (`+07:00`) hoặc UTC (`Z`). Truy vấn dùng
`received_at`, không dùng uptime `device_ts_ms`.

## Vẽ biểu đồ - Giai đoạn 6

Vẽ dữ liệu một giờ gần nhất và đồng thời xuất CSV:

```powershell
.\.venv\Scripts\python.exe .\analysis\plot_data.py `
  --device-id esp32_dht11 `
  --last-hours 1
```

Kết quả được ghi vào:

- `results/chart_temperature.png`
- `results/chart_humidity.png`
- `results/telemetry_export.csv`

Các phép đo `NULL` không bị đổi thành 0. Điểm `SUSPECT` dùng marker tam giác màu
cam; lần đọc `INVALID_SENSOR` được đánh dấu `x` tại thời gian nhận và không được
coi là một giá trị đo.

## Restart test - Giai đoạn 7

Đảm bảo ESP32 và Mosquitto đang hoạt động, đồng thời không chạy một ingestion
service khác. Sau đó chạy:

```powershell
.\.venv\Scripts\python.exe .\analysis\restart_test.py
```

Script tự thực hiện:

1. Khởi động ingestion và chốt T0.
2. Thu dữ liệu thật trong 10 giây, dừng ingestion và chốt T1.
3. Truy vấn đúng cửa sổ cố định T0-T1 và lưu snapshot trước restart.
4. Khởi động lại ingestion, sau đó dừng lần nữa.
5. Truy vấn lại chính xác T0-T1 và so sánh toàn bộ khóa/giá trị.

Kết quả:

- `results/log_before_restart.txt`
- `results/log_after_restart.txt`
- `results/restart_log.txt`
- `results/restart_ingest_before.log`
- `results/restart_ingest_after.log`

Đạt khi số dòng, tập khóa và toàn bộ giá trị đều giống hệt trước/sau restart.

## Concurrent test - Giai đoạn 8

Đảm bảo ESP32 và Mosquitto đang chạy, đồng thời dừng ingestion service thông
thường để hai consumer không làm kết quả khó theo dõi. Chạy:

```powershell
$env:MPLBACKEND = 'Agg'
.\.venv\Scripts\python.exe .\analysis\concurrent_test.py --duration 20
```

Script chạy hai phép thử bằng dữ liệu MQTT thật:

- A: ghi SQLite, không có truy vấn nặng.
- B: ghi SQLite trong khi một thread lặp liên tục truy vấn aggregate.

Kết quả:

- `results/concurrent_test.csv`
- `results/concurrent_test.png`

CSV ghi tổng bản tin nhận/lưu/từ chối/trùng, lỗi database, độ trễ ghi trung
bình/P95, số truy vấn, lỗi truy vấn và độ trễ truy vấn trung bình/P95. Kết quả
chỉ phản ánh điều kiện phần cứng và thời lượng được ghi trong CSV.

