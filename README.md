# 🍪 CookieGli

<p align="center">
  <strong>Bộ công cụ nén ngữ cảnh kiến trúc và quản lý kinh nghiệm cho AI Coding Agents</strong><br>
  <em>Thuần Python stdlib • Không cài thêm thư viện phụ thuộc • Chạy nhẹ nhàng trên Windows, Linux, macOS</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.2.0-blue.svg?style=flat-square" alt="Version 2.2.0">
  <img src="https://img.shields.io/badge/python-%E2%89%A53.9-blue.svg?style=flat-square" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/tests-32%2F32%20passing-brightgreen.svg?style=flat-square" alt="Tests Passing">
  <img src="https://img.shields.io/badge/monorepo-ready-purple.svg?style=flat-square" alt="Monorepo Ready">
  <img src="https://img.shields.io/badge/mcp-ready-darkgreen.svg?style=flat-square" alt="MCP Ready">
  <img src="https://img.shields.io/badge/dependencies-0%20(stdlib%20only)-orange.svg?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="MIT License">
</p>

---

## 📑 Mục Lục (Table of Contents)
- [1. CookieGli Giải Quyết Vấn Đề Gì? (Why CookieGli?)](#1-cookiegli-giải-quyết-vấn-đề-gì-why-cookiegli)
- [2. Cách Hoạt Động (How It Works)](#2-cách-hoạt-động-how-it-works)
- [3. Các Tính Năng Hữu Ích (Key Features)](#3-các-tính-năng-hữu-ích-key-features)
- [4. Bảng So Sánh Nhanh (Feature Matrix)](#4-bảng-so-sánh-nhanh-feature-matrix)
- [5. Cài Đặt & Dùng Nhanh (Quick Start)](#5-cài-đặt--dùng-nhanh-quick-start)
- [6. Tra Cứu Lệnh CLI (CLI Reference)](#6-tra-cứu-lệnh-cli-cli-reference)
- [7. Cơ Chế Tính Điểm Hữu Ích (ROI Dynamics)](#7-cơ-chế-tính-điểm-hữu-ích-roi-dynamics)
- [8. Hướng Dẫn Dành Cho AI Agent (.agents Standard)](#8-hướng-dẫn-dành-cho-ai-agent-agents-standard)
- [9. Kiểm Thử (Tests & Verification)](#9-kiểm-thử-tests--verification)
- [10. Đóng Góp & Giấy Phép (License)](#10-đóng-góp--giấy-phép-license)

---

## 1. CookieGli Giải Quyết Vấn Đề Gì? (Why CookieGli?)

Khi làm việc với các AI agent hỗ trợ lập trình (Claude Code, OpenAI Codex, Antigravity, Cursor, Windsurf...), một vấn đề rất hay gặp phải là **phình to ngữ cảnh (Context Bloat)**:
* Nạp cả cây thư mục hoặc đọc nhiều file mã nguồn thô làm tiêu tốn từ vài chục ngàn đến cả trăm ngàn token ngay từ những câu hỏi đầu tiên. Việc này vừa tốn chi phí API, vừa làm mô hình dễ bị loãng thông tin và nhanh quên ngữ cảnh quan trọng.
* Sau khi AI giúp bạn sửa xong một lỗi hóc búa, sang phiên làm việc tiếp theo agent thường không nhớ cách xử lý đó và rất dễ lặp lại cùng một sai lầm.

**CookieGli được tạo ra như một công cụ hỗ trợ nhỏ gọn để giải quyết hai việc đó:**
1. **Nén bản đồ kiến trúc (< 600 tokens):** Phân tích các class, hàm, phương thức chính thành một bản đồ súc tích để nạp cho AI trong chớp mắt.
2. **Hỗ trợ Monorepo theo phân cấp:** Chia bản đồ thành tầng tổng quan (Root Map) và từng gói nhỏ (Package Leaf), làm việc ở gói nào chỉ nạp gói đó.
3. **Bộ nhớ đệm SQLite nhẹ nhàng:** Lưu hash file để nhận biết thay đổi, file nào chưa sửa thì bỏ qua không quét lại.
4. **Ghi nhớ bài học thực chiến (Darwin Memory):** Giữ lại các quy tắc đã kiểm chứng, tự động giảm dần điểm những kinh nghiệm lâu ngày không dùng đến.
5. **Đồng bộ với nhiều loại agent:** Tự động tạo định dạng phù hợp cho Claude Code, Codex, Antigravity, Cursor, Windsurf hoặc chạy thành máy chủ MCP chuẩn.
6. **Thuần Python stdlib:** Không cần cài thêm thư viện phụ thuộc (`zero pip install`), chạy an toàn trên Windows, Linux và macOS.

---

## 2. Cách Hoạt Động (How It Works)

<p align="center">
  <img src="assets/architecture.svg" alt="CookieGli Core Architecture" width="100%">
</p>

```text
[ Mã nguồn dự án (~30k - 100k Tokens) ]
                 │
                 ▼
[ Bước 1: AstScanner ] ── Lưu cache SQLite WAL nhẹ nhàng
                 │
                 ▼
[ Bước 2: GenomeEngine / MonorepoEngine ] ── Lập bản đồ phân cấp
                 │
                 ▼
[ Kết quả: GENOME.md ] ── ≤ 500 - 600 Tokens (tiết kiệm ~96% token)
                 │
                 ▼
[ AI Agent làm việc & kiểm thử ] ── Test tự động bảo đảm chất lượng
                 │
                 ▼
[ DarwinMemory ] ── Lưu kinh nghiệm, tính điểm hữu ích và đào thải tự nhiên
```

---

## 3. Các Tính Năng Hữu Ích (Key Features)

### 📁 1. Hỗ Trợ Dự Án Monorepo Nhiều Gói (Hierarchical Monorepo)
Với các repository chia thành nhiều package/service con (`packages/*`, `apps/*`, `services/*`):
* **Root Map (~300 tokens):** Cung cấp cái nhìn tổng quan về danh sách các gói và quan hệ phụ thuộc cơ bản giữa chúng.
* **Package Leaf (~500 tokens):** Mỗi gói giữ một bản tóm tắt kiến trúc riêng biệt.
* Khi bạn yêu cầu AI sửa một module cụ thể, hệ thống chỉ nạp đúng phần liên quan thay vì đọc cả dự án, giúp tiết kiệm đáng kể token cho mỗi lượt chat.

### ⚡ 2. Bộ Nhớ Đệm SQLite Nhẹ Nhàng (Incremental Cache)
* Lưu cấu trúc và mã băm SHA-256 vào file database SQLite nhỏ gọn (`.cookiegli/ast_cache.db`).
* Khi bạn thay đổi 1 vài file, bộ quét chỉ phân tích lại đúng các file đó trong vài mili-giây, không quét lại toàn bộ kho mã nguồn.

### 🧠 3. Ghi Nhớ Kinh Nghiệm & Đào Thải Tự Nhiên (Darwin Memory)
* **Gắn nhãn phạm vi (Scope):** Các bài học được gắn nhãn cụ thể (`backend.auth`, `frontend.react`, `database`) để tránh áp dụng nhầm chỗ.
* **Tự giảm điểm theo thời gian:** Những bài học hữu ích, dùng thường xuyên sẽ giữ điểm cao; những kinh nghiệm lâu ngày không đụng đến sẽ tự giảm dần độ ưu tiên để nhường chỗ cho kiến thức mới.

### 🔄 4. Đồng Bộ Với Các AI Agent Phổ Biến (Target Adapters)
Tự động đồng bộ bản đồ kiến trúc và bài học kinh nghiệm vào đúng định dạng mà agent của bạn sử dụng:
* **Claude Code (`CLAUDE.md`)**: Hỗ trợ tận dụng cơ chế Prompt Cache của Claude.
* **OpenAI Codex (`AGENTS.md`)**: Cung cấp cấu trúc rõ ràng cho các mô hình lập trình của OpenAI.
* **Google Antigravity (`.agents/GENOME.md`, `.agents/AGENTS.md`)**: Chuẩn hóa pipeline tự động hóa.
* **Cursor & Windsurf (`.cursorrules`, `.windsurfrules`)**: Tự động sinh chỉ dẫn điều hướng mã nguồn.

### 🔌 5. Máy Chủ MCP Chuẩn (Model Context Protocol)
Tích hợp sẵn server MCP chạy qua giao thức STDIO JSON-RPC 2.0:
* Khởi chạy đơn giản: `python cli/cookiegli.py mcp`
* Cung cấp sẵn các công cụ để agent gọi: lấy genome dự án, tổng hợp ngữ cảnh theo task, lưu kinh nghiệm, tìm kiếm bài học và đồng bộ cấu hình.

---

## 4. Bảng So Sánh Nhanh (Feature Matrix)

| Tiêu chí | Đọc file thô truyền thống | Bộ lọc regex đơn giản | 🍪 CookieGli |
|---|---|---|---|
| **Lượng token tiêu thụ** | 30.000 – 100.000 tokens | 5.000 – 10.000 tokens | **300 – 600 tokens** |
| **Phân tích cấu trúc hàm/class** | ❌ Đọc thủ công | ⚠️ Dễ sót cú pháp mới | ✅ **Phân tích cây AST thực tế** |
| **Hỗ trợ Monorepo** | ❌ Không | ❌ Không | ✅ **Chia tầng Root & Package** |
| **Bộ nhớ đệm quét nhanh** | ❌ Quét lại từ đầu | ❌ Không có | ✅ **SQLite WAL (<5ms khi sửa file)** |
| **Tương thích Windows / Linux / macOS** | Phụ thuộc tool | Dễ lỗi lệnh shell Unix | ✅ **100% Python stdlib an toàn** |
| **Lọc file nén / minified** | ❌ Dễ đọc nhầm | ❌ Không có | ✅ **Tự nhận diện và bỏ qua** |
| **Ghi nhớ bài học fix bug** | ❌ Quên sau mỗi phiên | ❌ Không có | ✅ **Darwin Memory + Giảm điểm tự nhiên** |
| **Độ phức tạp cài đặt** | N/A | Cần nhiều package | ✅ **Zero Dependency (chạy ngay)** |

---

## 5. Cài Đặt & Dùng Nhanh (Quick Start)

### Yêu cầu:
* Python $\ge 3.9$ (đã test kỹ từ Python 3.9 đến 3.14).
* Không cần cài thêm bất kỳ thư viện ngoài nào (`zero dependencies`).

### Tải dự án về:
```bash
git clone https://github.com/LoveCookieee-java/CookieGli.git
cd CookieGli
```

### 1. Tạo bản đồ kiến trúc dự án (Genome):
```bash
# Cho dự án thông thường:
python cli/cookiegli.py genome build . --save .agents/GENOME.md

# Cho Monorepo có nhiều gói:
python cli/cookiegli.py monorepo build . --save .agents/GENOME.md
```

### 2. Lấy ngữ cảnh cho một công việc cụ thể:
```bash
# Trích xuất đúng các class/hàm liên quan đến task:
python cli/cookiegli.py genome context "Sửa hàm xác thực token người dùng"
```

### 3. Lưu và quản lý kinh nghiệm (Darwin Memory):
```bash
# Lưu một bài học mới kèm nhãn:
python cli/cookiegli.py darwin register jwt_check pattern "Luôn kiểm tra hạn dùng exp trước khi giải mã token" --scope "backend.auth" --tags "auth,security"

# Ghi nhận kết quả khi áp dụng (thành công = true, thất bại = false):
python cli/cookiegli.py darwin use <artifact_id> true

# Tìm kiếm bài học:
python cli/cookiegli.py darwin search --scope "backend" --tags "auth"

# Tự động cập nhật bài học vào file .agents/AGENTS.md:
python cli/cookiegli.py darwin sync
```

### 4. Đồng bộ nhanh sang các môi trường khác:
```bash
# Đồng bộ một lượt cho tất cả các agent (Claude, Codex, Antigravity, Cursor, Windsurf):
python cli/cookiegli.py sync --target all --root .
```

---

## 6. Tra Cứu Lệnh CLI (CLI Reference)

Mọi thao tác đều thực hiện qua script `cli/cookiegli.py`:

### 🧬 Genome Engine (`cookiegli genome`)
| Lệnh | Tham số | Ý nghĩa |
|---|---|---|
| `build` | `[path] [--max-tokens 1500] [--save PATH] [--no-cache]` | Quét mã nguồn và tạo bản đồ nén kiến trúc. |
| `context` | `<task> [path] [--max-tokens 1200] [--no-cache]` | Lấy lát cắt ngữ cảnh theo từ khóa công việc. |

### 📁 Monorepo Engine (`cookiegli monorepo`)
| Lệnh | Tham số | Ý nghĩa |
|---|---|---|
| `build` | `[path] [--max-tokens 400] [--max-files 20000] [--save PATH]` | Tạo bản đồ tổng quan mức Root cho dự án Monorepo. |
| `context` | `<task> [path] [--max-tokens 1200] [--max-files 20000]` | Kết hợp ngữ cảnh từ Root Map và Package liên quan. |

### 🧠 Darwin Memory (`cookiegli darwin`)
| Lệnh | Tham số | Ý nghĩa |
|---|---|---|
| `register` | `<name> <type> <content> [--scope SCOPE] [--tags TAGS]` | Thêm bài học mới (`pattern`, `lesson`, `skill`, `tool`). |
| `use` | `<artifact_id> [true\|false]` | Ghi nhận lần sử dụng thành công hoặc thất bại. |
| `search` | `[--query TEXT] [--scope SCOPE] [--tags TAGS]` | Tìm kiếm bài học theo từ khóa, phạm vi hoặc thẻ. |
| `list` | `[type] [--scope SCOPE]` | Xem danh sách bài học đang lưu, xếp theo điểm hữu ích. |
| `evolve` | `[--threshold 0.3] [--max-capacity 50] [--decay 0.95] [--half-life DAYS]` | Chạy chu kỳ giảm điểm bài học ít dùng và dọn bài học điểm thấp. |
| `sync` | `[--agents-file PATH] [--scope SCOPE] [--max-tokens 500]` | Đẩy các bài học điểm cao vào file `.agents/AGENTS.md`. |

### 🔄 Đồng Bộ Hóa (`cookiegli sync`)
| Lệnh | Tham số | Ý nghĩa |
|---|---|---|
| `sync` | `[--target TARGET] [--root PATH] [--no-genome] [--no-darwin]` | Đồng bộ vào `claude`, `codex`, `antigravity`, `cursor`, `windsurf` hoặc `all`. |

### 🔌 Máy Chủ MCP (`cookiegli mcp`)
| Lệnh | Tham số | Ý nghĩa |
|---|---|---|
| `mcp` | `[--root PATH]` | Khởi động server MCP qua STDIO để các AI tool kết nối. |

---

## 7. Cơ Chế Tính Điểm Hữu Ích (ROI Dynamics)

Để đánh giá một bài học có thực sự đáng tin cậy hay không, CookieGli dùng công thức làm mượt **Laplace Smoothing** kết hợp chu kỳ giảm điểm theo thời gian:

$$\text{Tỷ lệ thành công mượt} = \frac{\text{Số lần thành công} + 1}{\text{Tổng số lần dùng} + 2}$$

$$\text{Điểm ROI} = \left(0.7 \times \text{Tỷ lệ mượt} + 0.3 \times \min\left(\frac{\text{Số lần dùng}}{5}, 1.0\right)\right) \times 2^{-\frac{\Delta t}{t_{1/2}}}$$

**Cách tính này giúp giải quyết 2 việc:**
1. **Tránh kết luận vội vã:** Một quy tắc mới dùng 1 lần thành công sẽ không bị đẩy điểm lên 100% ngay, mà cần qua vài lần kiểm chứng thực tế để khẳng định độ tin cậy.
2. **Không để bộ nhớ bị cũ:** Sau một thời gian không đụng đến (mặc định $t_{1/2} = 30$ ngày), điểm bài học sẽ giảm dần. Nếu bài học không còn phù hợp và rớt xuống dưới ngưỡng sàn (`0.30`), nó sẽ được dọn đi để giữ cho bộ nhớ luôn gọn gàng.

---

## 8. Hướng Dẫn Dành Cho AI Agent (.agents Standard)

Nếu bạn dùng AI agent tự động, tệp [`.agents/AGENTS.md`](.agents/AGENTS.md) giúp định hướng hành vi:
1. **Nắm tổng thể trước:** Đọc `.agents/GENOME.md` ở đầu phiên làm việc để hiểu cấu trúc toàn bộ dự án mà chỉ tốn vài trăm token.
2. **Đọc đúng chỗ cần sửa:** Thay vì nạp cả file lớn, hãy đọc theo phạm vi dòng (`StartLine` / `EndLine`) hoặc dùng công cụ tìm kiếm chuẩn xác.
3. **Chạy test tự động:** Luôn chạy lại test suite sau khi sửa code để đảm bảo không phát sinh lỗi ngoài ý muốn.
4. **Đúc kết kinh nghiệm:** Khi giải quyết xong một lỗi hóc búa, tự ghi lại bài học vào bảng Darwin để lần sau không vấp phải.

---

## 9. Kiểm Thử (Tests & Verification)

Dự án đi kèm bộ 32 bài kiểm thử tự động, sử dụng trực tiếp thư viện chuẩn `unittest` của Python (không cần cài pytest hay thư viện phụ trợ):

```bash
python -m unittest discover -s tests -v
```

```text
Ran 32 tests in 0.828s

OK (32/32 Tests Pass 100%)
```

---

## 10. Đóng Góp & Giấy Phép (License)

CookieGli là một dự án mã nguồn mở còn mới. Mọi đóng góp, ý kiến phản hồi hoặc báo lỗi qua GitHub Issues / Pull Requests đều rất được trân trọng!

Dự án được phát hành dưới giấy phép mã nguồn mở [MIT License](LICENSE) © 2026 LoveCookieee (KhoaSuperT1). Tự do sử dụng, tùy biến và tích hợp vào các dự án cá nhân hoặc công việc hàng ngày.

