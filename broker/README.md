# Giai đoạn 2 - Mosquitto Broker trên Windows 11

Giai đoạn này chỉ cấu hình và kiểm tra MQTT Broker. ESP32 chưa kết nối Wi-Fi và
chưa publish MQTT; các thay đổi firmware đó thuộc Giai đoạn 3.

## Cấu hình

- TCP port: `1883`
- Listener: `0.0.0.0` (cho phép ESP32 kết nối qua IPv4 LAN của laptop)
- Topic dự kiến: `cse3069/th05/esp32/telemetry`
- Anonymous access: bật để thử nghiệm nhanh trong mạng lab tin cậy
- Persistence của broker: tắt; dữ liệu bền vững sẽ được lưu bằng SQLite ở giai
  đoạn sau

Không mở port 1883 trực tiếp ra Internet. Khi triển khai ngoài mạng lab, cần
thêm tài khoản/mật khẩu và TLS.

## 1. Chạy broker

Mở PowerShell tại thư mục gốc dự án:

```powershell
& 'D:\Program Files\mosquitto\mosquitto.exe' -c '.\broker\mosquitto.conf' -v
```

Giữ cửa sổ này chạy. Dòng sau cho biết broker đã mở cổng thành công:

```text
Opening ipv4 listen socket on port 1883.
```

Nếu báo `Address already in use`, một Mosquitto service hoặc chương trình khác
đang dùng cổng 1883. Không chạy thêm broker thứ hai trên cùng cổng.

## 2. Test subscriber

Mở PowerShell thứ hai:

```powershell
& 'D:\Program Files\mosquitto\mosquitto_sub.exe' `
  -h 127.0.0.1 -p 1883 `
  -t 'cse3069/th05/esp32/telemetry' -q 1 -v
```

## 3. Test publisher

Mở PowerShell thứ ba:

```powershell
& 'D:\Program Files\mosquitto\mosquitto_pub.exe' `
  -h 127.0.0.1 -p 1883 `
  -t 'cse3069/th05/esp32/telemetry' -q 1 `
  -m '{\"source\":\"phase2_test\",\"message\":\"hello\"}'
```

Các dấu `\"` là cần thiết khi gọi file `.exe` native từ Windows PowerShell để
payload đến broker vẫn giữ dấu ngoặc kép hợp lệ của JSON.

Subscriber phải nhận đúng một dòng tương tự:

```text
cse3069/th05/esp32/telemetry {"source":"phase2_test","message":"hello"}
```

## 4. Lấy IPv4 LAN cho Giai đoạn 3

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.InterfaceOperationalStatus -eq 'Up' } |
  Select-Object InterfaceAlias, IPAddress
```

Chọn IPv4 của Wi-Fi/Ethernet đang cùng mạng với ESP32. ESP32 phải dùng địa chỉ
này, không dùng `localhost` hoặc `127.0.0.1`.

## 5. Windows Firewall

Nếu test trên chính laptop thành công nhưng thiết bị khác không kết nối được,
Windows Firewall có thể đang chặn inbound TCP 1883. Chỉ tạo inbound rule cho
**Private network** khi chuẩn bị Giai đoạn 3; không mở cho Public network.

## Tiêu chí hoàn tất Giai đoạn 2

1. Broker khởi động không lỗi trên port 1883.
2. `mosquitto_sub` kết nối và subscribe thành công.
3. `mosquitto_pub` gửi QoS 1 và subscriber nhận đúng payload.
4. Xác định được IPv4 LAN của laptop để dùng ở Giai đoạn 3.

