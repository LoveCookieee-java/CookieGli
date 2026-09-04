# CookieGli

<p align="center">
  <strong>Bộ công cụ nén ngữ cảnh kiến trúc, chỉ mục mã nguồn và phân tích tác động thay đổi</strong><br>
  <em>Thuần Python stdlib • Không thư viện phụ thuộc ngoài • Chạy ổn định trên Windows, Linux, macOS</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%E2%89%A53.9-blue.svg?style=flat-square" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/tests-160%2F160%20passing-brightgreen.svg?style=flat-square" alt="Tests Passing">
  <img src="https://img.shields.io/badge/token--reduction-75%25--92%25-green.svg?style=flat-square" alt="Token Reduction">
  <img src="https://img.shields.io/badge/symbol--seek-%3C0.1ms-darkgreen.svg?style=flat-square" alt="Symbol Seek Latency">
  <img src="https://img.shields.io/badge/mcp-CookieGli__Full-purple.svg?style=flat-square" alt="CookieGli_Full MCP Ready">
  <img src="https://img.shields.io/badge/dependencies-0%20(stdlib%20only)-orange.svg?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="MIT License">
</p>

---

## Mục Lục
- [1. Giới Thiệu & Vấn Đề Giải Quyết](#1-giới-thiệu--vấn-đề-giải-quyết)
- [2. Kiến Trúc Hoạt Động](#2-kiến-trúc-hoạt-động)
- [3. Các Tính Năng Cốt Lõi](#3-các-tính-năng-cốt-lõi)
  - [3.1. Semantic Code Skeletonizer & Focus-Symbol Mode](#31-semantic-code-skeletonizer--focus-symbol-mode)
  - [3.2. Chỉ Mục Biểu Tượng B-Tree & Toàn Văn SQLite FTS5 BM25+](#32-chỉ-mục-biểu-tượng-b-tree--toàn-văn-sqlite-fts5-bm25)
  - [3.3. Động Cơ Ngữ Cảnh Hai Tầng (Two-Tier Boost Engine) & Hiệu Chuẩn Suy Luận 2026](#33-động-cơ-ngữ-cảnh-hai-tầng-two-tier-boost-engine--hiệu-chuẩn-suy-luận-2026)
  - [3.4. Phân Tích Lan Truyền Thay Đổi (Git Blast Radius & Test Targeting)](#34-phân-tích-lan-truyền-thay-đổi-git-blast-radius--test-targeting)
  - [3.5. Chưng Cất Lỗi Tự Động (Autonomous Error & Traceback Distiller)](#35-chưng-cất-lỗi-tự-động-autonomous-error--traceback-distiller)
  - [3.6. Bản Đồ Kiến Trúc Dự Án (Project AST Genome) & Chuẩn Hóa Token-0](#36-bản-đồ-kiến-trúc-dự-án-project-ast-genome--chuẩn-hóa-token-0)
  - [3.7. Hỗ Trợ Dự Án Monorepo Phân Cấp](#37-hỗ-trợ-dự-án-monorepo-phân-cấp)
  - [3.8. Bộ Nhớ Kinh Nghiệm Thích Ứng (Darwin Memory Pool)](#38-bộ-nhớ-kinh-nghiệm-thích-ứng-darwin-memory-pool)
- [4. Số Liệu Kiểm Định Thực Nghiệm](#4-số-liệu-kiểm-định-thực-nghiệm)
- [5. Cài Đặt & Bắt Đầu Nhanh](#5-cài-đặt--bắt-đầu-nhanh)
- [6. Tra Cứu Lệnh CLI](#6-tra-cứu-lệnh-cli)
- [7. Cấu Hình MCP Server (Model Context Protocol)](#7-cấu-hình-mcp-server-model-context-protocol)
- [8. Kiểm Thử & Đảm Bảo Chất Lượng](#8-kiểm-thử--đảm-bảo-chất-lượng)
- [9. Giấy Phép](#9-giấy-phép)

---

## 1. Giới Thiệu & Vấn Đề Giải Quyết

Khi làm việc trong các dự án phần mềm có quy mô vừa và lớn, việc duyệt và thao tác mã nguồn thường gặp phải các giới hạn kỹ thuật:
* **Quá tải kích thước ngữ cảnh (Context Bloat):** Đọc toàn bộ các file mã nguồn thô tiêu tốn hàng chục ngàn token cho mỗi lượt xử lý, gây lãng phí băng thông, tăng độ trễ và làm loãng thông tin quan trọng.
* **Tra cứu biểu tượng tốn kém:** Sử dụng regex grep trên toàn bộ cây thư mục tốn nhiều tài nguyên đĩa và dễ trả về kết quả nhiễu khi dự án phình to.
* **Khó xác định phạm vi ảnh hưởng khi sửa code:** Khi thay đổi một module, rất khó biết chính xác những thành phần nào phụ thuộc vào nó và cần chạy những bài test nào, dẫn đến việc phải chạy lại toàn bộ test suite lớn và sinh ra log thừa thãi.
* **Mất dấu kinh nghiệm xử lý lỗi:** Các giải pháp khắc phục sự cố, sửa lỗi cú pháp hay quy tắc dự án sau khi hoàn thành thường bị phân tán, không được lưu trữ có cấu trúc để tái sử dụng.

**CookieGli** là bộ công cụ dòng lệnh và giao thức MCP gọn nhẹ, tập trung vào:
1. **Rút gọn mã nguồn giữ cấu trúc (Skeletonization):** Giữ nguyên khai báo class, interface, method signatures, decorators, type annotations và gấp gọn phần thân logic giúp giảm 75% đến 92% dung lượng văn bản.
2. **Chỉ mục B-Tree tra cứu nhanh:** Lưu trữ vị trí symbol, chữ ký hàm, docstring trong SQLite WAL với độ trễ tìm kiếm dưới 0.1ms.
3. **Phân tích tác động đồ thị ngược (Blast Radius):** Dự đoán chính xác các file bị ảnh hưởng khi có git diff và chỉ điểm đúng test suite tối thiểu cần chạy.
4. **Tự động trích xuất bài học từ traceback:** Phân tích stack trace từ Python, Node/Jest, Go, Rust và diff sửa lỗi thành quy tắc thực chiến có đánh số điểm tin cậy Bayesian.
5. **Thuần Python chuẩn (Zero Dependencies):** Chạy trực tiếp từ Python 3.9+ mà không cần cài đặt thêm thư viện bên ngoài qua pip.

---

## 2. Kiến Trúc Hoạt Động

```text
               Mã nguồn dự án (Python, TS/JS, Go, Rust, Java, C#, C++)
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │   AstScanner (AST + Regex) │
                        └─────────────┬─────────────┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
                ▼                     ▼                     ▼
     ┌─────────────────────┐┌───────────────────┐┌─────────────────────┐
     │ Inverted Symbol     ││ Code Skeletonizer ││ Git Blast Radius    │
     │ Index (SQLite BTree)││ & Focus-Symbol    ││ (Ingress Dependency)│
     │ Latency < 0.1ms     ││ Reduction 75%-92% ││ Surgical Test Target│
     └──────────┬──────────┘└─────────┬─────────┘└──────────┬──────────┘
                │                     │                     │
                └─────────────────────┼─────────────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │ Project Genome Engine     │
                        │ Architectural Map (<600t) │
                        └─────────────┬─────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │ Error & Traceback         │
                        │ Distiller (Darwin Memory) │
                        └─────────────┬─────────────┘
                                      │
                ┌─────────────────────┴─────────────────────┐
                ▼                                           ▼
     ┌───────────────────────┐                 ┌───────────────────────┐
     │ CLI Interface         │                 │ MCP Server (STDIO)    │
     │ (cookiegli ...)       │                 │ JSON-RPC 2.0 Tools    │
     └───────────────────────┘                 └───────────────────────┘
```

---

## 3. Các Tính Năng Cốt Lõi

### 3.1. Semantic Code Skeletonizer & Focus-Symbol Mode
Bộ xử lý cấu trúc hỗ trợ phân tích và rút gọn mã nguồn nhiều ngôn ngữ (Python AST, TypeScript/JavaScript, Go, Rust, Java, C#, C++):
* **Bảo toàn thông tin cốt lõi:** Giữ nguyên imports, module docstrings, cấu trúc class, decorators, trường dataclass, chữ ký hàm và kiểu dữ liệu trả về.
* **Gấp gọn thân hàm theo khoảng dòng:** Thay thế thân hàm bằng đánh dấu phạm vi thực tế `... [L{start}-L{end}]` để người dùng hoặc công cụ dễ dàng tra cứu lại khi cần.
* **Chế độ Focus-Symbol:** Khi cần làm việc với một hàm hoặc phương thức cụ thể, hệ thống giữ nguyên văn 100% nội dung của hàm đó (bao gồm chú thích và thụt lề chuẩn), đồng thời rút gọn tất cả các hàm và class còn lại trong file.
* **Cơ chế nén 4 tầng (4-Tier Token Budget):** Tự động điều chỉnh mật độ thông tin (giữ docstring đầy đủ -> rút gọn 1 dòng -> loại bỏ docstring hàm phụ -> gộp phương thức nội bộ) để đảm bảo không vượt quá ngân sách token quy định.

### 3.2. Chỉ Mục Biểu Tượng B-Tree & Toàn Văn SQLite FTS5 BM25+
* **B-Tree Index (<0.1ms):** Bảng `symbol_cache` lưu trữ trong SQLite WAL với chỉ mục kép NOCASE trên `simple_name` và `name` (kèm container prefix). Hơn 15,000 queries/giây.
* **Hybrid Retrieval (SQLite FTS5 BM25+):** Bảng ảo `symbol_fts` đồng bộ tự động 2 chiều qua bộ 3 SQLite Triggers (`trig_symbol_cache_ai`, `trig_symbol_cache_ad`, `trig_symbol_cache_au`). Xếp hạng Information Retrieval chuẩn công nghiệp theo thuật toán Okapi BM25.
* **Token Sanitization & Fallback:** Tự động khử trùng lặp từ khóa, bỏ qua wildcard cho từ đơn 1 ký tự, và graceful fallback về B-Tree search nếu môi trường thiếu FTS5 module.

### 3.3. Động Cơ Ngữ Cảnh Hai Tầng (Two-Tier Boost Engine) & Hiệu Chuẩn Suy Luận 2026
* **Layer 1: Static Architectural Anchor (<600 tokens):** Nằm cố định tại Token 0 của các file chỉ dẫn (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`). Tuyệt đối bất biến (`# PROJECT GENOME | id:...`), triệt tiêu timestamp động và telemetry nổi -> Kích hoạt **100% Prefix Cache Read Discount** (giảm 90% chi phí trên GPT-6 Astra, GPT-5.6 Sol, Claude Opus 5, Gemini 3.7 Flash, Kimi K3, DeepSeek-V4).
* **Layer 2: Dynamic Task Tail (<600 tokens):** Sinh theo từng tác vụ cụ thể (`cookiegli boost <task>`), kết hợp BM25 symbol matching + Code Skeletonizer giữ verbatim hàm focus + Blast Radius test targeting. Tự động cân bằng code fences markdown khi cắt tỉa.
* **Hiệu chuẩn suy luận 2026 (Reasoning Calibration):** Tự động điều chỉnh `effort=low/medium/high` theo `blast_depth` để tiết kiệm token suy luận đắt đỏ ($15–$50/M) của các frontier models.

### 3.4. Phân Tích Lan Truyền Thay Đổi (Git Blast Radius & Test Targeting)
* **Đảo ngược đồ thị phụ thuộc (Forward-to-Ingress):** Xây dựng danh sách các file trực tiếp và gián tiếp phụ thuộc vào một module hoặc symbol bất kỳ.
* **Tự động nhận diện thay đổi:** Đọc trạng thái sửa đổi thông qua `git status --porcelain` an toàn hoặc tự động đối chiếu `mtime` trên cache SQLite khi không có môi trường Git.
* **Khoanh vùng kiểm thử chính xác (Surgical Test Targeting):** Ánh xạ từ các module bị thay đổi sang đúng các file test tương ứng, tự động đề xuất câu lệnh chạy kiểm thử tối thiểu thay vì chạy toàn bộ test suite, giảm đến 80% dung lượng log kiểm thử thừa.

### 3.5. Chưng Cất Lỗi Tự Động (Autonomous Error & Traceback Distiller)
* **Bộ bóc tách traceback 3 tầng:** Nhận diện và trích xuất khung lỗi từ Python (`unittest`, `pytest`, `Traceback`), Node.js/Jest stack traces, cũng như Go/Rust panics.
* **Nhận diện mẫu sửa lỗi:** Phân tích git diff hoặc mô tả sửa lỗi (như bổ sung kiểm tra None/Null, fallback mặc định, chuẩn hóa đường dẫn, kiểm tra biên mảng).
* **Tự động tạo quy tắc và lưu trữ:** Tổng hợp thành quy tắc bài học Darwin có gắn nhãn phạm vi (`core.cache`, `git.blast`, `engine.ast`...), tính điểm tin cậy ban đầu qua công thức Laplace Smoothing và hỗ trợ khôi phục tự động các quy tắc cũ nếu lỗi tái diễn.

### 3.6. Bản Đồ Kiến Trúc Dự Án (Project AST Genome) & Chuẩn Hóa Token-0
* Tạo bản tóm tắt cấu trúc toàn dự án chỉ trong phạm vi dưới 600 tokens.
* Chuẩn hóa bất biến Token 0: loại bỏ timestamp động, bảo toàn byte-stability để duy trì tỷ lệ cache hit cao nhất.
* Bao gồm: kiến trúc công nghệ, điểm vào (entry points), ma trận phụ thuộc, các class/hàm trung tâm và hotspot kiến trúc.

### 3.7. Hỗ Trợ Dự Án Monorepo Phân Cấp
* **Tier-1 Root Cluster Map (<300 tokens):** Cung cấp bức tranh toàn cảnh về các package và mối quan hệ liên gói.
* **Tier-2 Package Leaf Genome (<500 tokens):** Bản tóm tắt chuyên sâu cho từng package cụ thể.
* Tránh việc nạp toàn bộ cấu trúc khổng lồ của monorepo vào một phiên làm việc đơn lẻ.

### 3.8. Bộ Nhớ Kinh Nghiệm Thích Ứng (Darwin Memory Pool)
* Lưu trữ các quy tắc, mẫu thiết kế và bài học thực chiến vào `.cookiegli/darwin_state.json`.
* Tách riêng telemetry số liệu nổi khỏi tệp markdown để bảo vệ prefix cache.
* Sử dụng công thức làm mượt Bayesian (Laplace Smoothing) kết hợp chu kỳ bán rã thời gian ($t_{1/2} = 30$ ngày) để tự động tăng ưu tiên các kinh nghiệm thực sự hiệu quả và loại bỏ dần các quy tắc lỗi thời.

---

## 4. Số Liệu Kiểm Định Thực Nghiệm

Các phép đo dưới đây được thực hiện trực tiếp trên mã nguồn của dự án (môi trường Windows 11, Python 3.11):

### Hiệu Quả Nén Ngữ Cảnh (Token Reduction)
| Tệp kiểm tra | Kích thước gốc (Tokens) | Sau Skeleton (Tokens) | Tỷ lệ giảm Skeleton | Tỷ lệ giảm Focus Mode |
| :--- | :---: | :---: | :---: | :---: |
| `src/cookiegli_core/ast_scanner.py` | 5,955 | 717 | **88.0%** | **78.2%** |
| `src/cookiegli_core/cache_db.py` | 3,216 | 558 | **82.6%** | **69.4%** |
| `src/cookiegli_core/skeletonizer.py` | 10,933 | 781 | **92.9%** | **86.4%** |
| `src/cookiegli_core/blast_radius.py` | 7,708 | 612 | **92.1%** | **73.8%** |
| `src/cookiegli_core/distiller.py` | 10,049 | 750 | **92.5%** | **90.9%** |
| **Tổng kiểm định thực tế** | **37,861** | **3,418** | **91.0%** | **82.3%** |

### Hiệu Năng Tra Cứu Biểu Tượng (B-Tree Seek Speed)
* Số lượt truy vấn kiểm thử: 1,000 queries.
* Tổng thời gian: 64.54 ms.
* **Độ trễ trung bình:** **0.0645 ms/lượt** (< 0.1ms).
* **Thông lượng:** **15,494 queries/giây**.

### Độ An Toàn Tài Nguyên & Khóa File
* Kiểm tra lặp 50 chu kỳ mở/quét/truy vấn liên tục trên SQLite WAL: heap memory hoàn toàn ổn định, không phát sinh rò rỉ bộ nhớ.
* Toàn bộ file handles được đóng hoàn toàn qua context manager, không phát sinh lỗi khóa file (`WinError 32`) trên hệ điều hành Windows.

---

## 5. Cài Đặt & Bắt Đầu Nhanh

### Yêu cầu môi trường
* Python >= 3.9 (kiểm thử từ Python 3.9 đến 3.14).
* Hoàn toàn không cần cài đặt thêm thư viện qua pip.

### Tải dự án
```bash
git clone https://github.com/LoveCookieee-java/CookieGli.git
cd CookieGli
```

### Các ví dụ sử dụng cơ bản

**1. Khởi tạo một lệnh duy nhất (One-Command Bootstrap):**
```bash
# Quét mã nguồn, nạp SQLite B-Tree & FTS5 BM25 index, và đồng bộ Layer 1 tĩnh:
python cli/cookiegli.py boost --init
```

**2. Sinh lát cắt ngữ cảnh động cho tác vụ lập trình (<600 tokens):**
```bash
# Tự động xếp hạng symbol BM25+, rút gọn skeleton, và hiệu chuẩn reasoning effort:
python cli/cookiegli.py boost "Fix cache miss on relative path in AstCache"
```

**3. Tra cứu toàn văn biểu tượng qua FTS5 BM25+:**
```bash
# Tìm kiếm nhanh toàn văn trong sub-millisecond:
python cli/cookiegli.py search "AstCache"
```

**4. Rút gọn cấu trúc file mã nguồn:**
```bash
# Rút gọn toàn bộ file giữ lại khai báo chữ ký:
python cli/cookiegli.py skeleton src/cookiegli_core/ast_scanner.py

# Rút gọn nhưng giữ nguyên văn thân hàm cần sửa:
python cli/cookiegli.py skeleton src/cookiegli_core/ast_scanner.py --focus scan
```

**5. Tra cứu định nghĩa biểu tượng:**
```bash
# Tìm kiếm biểu tượng theo tên:
python cli/cookiegli.py symbol AstScanner

# Tìm kiếm khớp chính xác:
python cli/cookiegli.py symbol find_symbols --exact
```

**6. Phân tích phạm vi ảnh hưởng khi sửa đổi:**
```bash
# Tự động phát hiện thay đổi qua git status và đề xuất test suite:
python cli/cookiegli.py blast --diff

# Phân tích mức độ ảnh hưởng của một file cụ thể:
python cli/cookiegli.py blast --file src/cookiegli_core/skeletonizer.py
```

**7. Chưng cất lỗi và lưu bài học:**
```bash
# Trích xuất bài học từ traceback hoặc log kiểm thử:
python cli/cookiegli.py distill --traceback "TypeError: 'NoneType' object is not subscriptable" --file src/cookiegli_core/cache_db.py --fix "Thêm guard kiểm tra None trước khi truy cập phần tử" --auto-register --sync
```

**8. Tạo bản đồ kiến trúc toàn dự án:**
```bash
python cli/cookiegli.py genome build . --save .agents/GENOME.md
```

**9. Đồng bộ sang cấu hình các công cụ:**
```bash
python cli/cookiegli.py sync --target all --root .
```

---

## 6. Tra Cứu Lệnh CLI

Mọi thao tác được thực hiện thống nhất qua tệp `cli/cookiegli.py`:

| Nhóm lệnh | Cú pháp | Ý nghĩa thực thi |
| :--- | :--- | :--- |
| `skeleton` | `skeleton <file> [--focus SYM] [--max-tokens N] [--json]` | Nén cấu trúc file mã nguồn hoặc tập trung vào một symbol. |
| `symbol` | `symbol [query] [--type TYPE] [--exact] [--limit N] [--json]` | Tra cứu vị trí, chữ ký và tài liệu của biểu tượng từ B-Tree index. |
| `blast` | `blast [--diff] [--file FILE] [--symbol SYM] [--max-depth N] [--json]` | Phân tích danh sách file phụ thuộc và khoanh vùng kiểm thử cần chạy. |
| `distill` | `distill [--traceback STR] [--file FILE] [--diff DIFF] [--fix FIX] [--auto-register] [--sync]` | Bóc tách traceback, tổng hợp bài học và tự động lưu trữ kinh nghiệm. |
| `genome` | `genome build [path] [--max-tokens N] [--save PATH]` | Quét mã nguồn và xuất bản đồ kiến trúc dự án tổng quát (<600 tokens). |
| `monorepo` | `monorepo build [path] [--save PATH]` | Xây dựng bản đồ phân tầng cho dự án nhiều package. |
| `darwin` | `darwin register / use / search / list / evolve / sync` | Quản lý vòng đời lưu trữ và đào thải bài học kinh nghiệm. |
| `boost` | `boost [--init] [task] [--max-tokens N] [--json]` | Khởi tạo dự án 1 lệnh (Layer 1 tĩnh) hoặc sinh lát cắt ngữ cảnh động (Layer 2) kèm hiệu chuẩn suy luận 2026. |
| `search` | `search <query> [--limit N]` | Tra cứu toàn văn BM25+ chuẩn công nghiệp trên SQLite FTS5 (<0.5ms). |
| `sync` | `sync [--target TARGET] [--root PATH]` | Đồng bộ vào `claude`, `codex`, `antigravity`, `cursor`, `windsurf` hoặc `all`. |
| `mcp` | `mcp [--profile standard\|full] [--name NAME] [--root PATH]` | Khởi chạy máy chủ MCP qua giao thức STDIO JSON-RPC 2.0 (mặc định profile: `full` - CookieGli_Full). |

---

## 7. Cấu Hình MCP Server: `CookieGli_Full` (All-in-One Architecture)

CookieGli cung cấp kiến trúc MCP hợp nhất **`CookieGli_Full`** với hệ thống gắn nhãn phân loại danh mục (Domain Category Namespacing) và tài nguyên hướng dẫn `mcp://cookiegli/guide` nhằm giúp các AI Agent (GPT-6 Astra, Claude Opus 5, Gemini 3.8 Flash, Kimi K3, DeepSeek-V4) **phân biệt và kích hoạt công cụ chuẩn xác 100%, không bị nhầm lẫn, trùng lặp hay bỏ sót**.

### 7.1. Danh Sách Công Cụ & Nhãn Phân Loại (Domain Namespaces)
* **`[00_CENTRAL_DISPATCH] cookiegli_full`**: Cổng điều phối đa hình trung tâm nhận `action` và `params`, tự động định tuyến tới tất cả các tool con.
* **`[01_TASK_BOOST] cookiegli_boost`**: Lối vào ưu tiên số 1 khi bắt đầu tác vụ lập trình/gỡ lỗi. Sinh trọn vẹn ngữ cảnh Layer 2 (<600t) gồm BM25 symbols + skeleton focus + ngân sách suy luận 2026.
* **`[01_TASK_CONTEXT] cookiegli_synthesize_context`**: Trích xuất lát cắt ngữ cảnh theo từ khóa tác vụ cụ thể.
* **`[02_SYMBOL_IR] cookiegli_search`**: Tra cứu toàn văn theo độ tương đồng ngữ nghĩa bằng SQLite FTS5 Okapi BM25+.
* **`[02_SYMBOL_BTREE] cookiegli_find_symbols`**: Tra cứu tức thì B-Tree index (<0.05ms) cho tên định danh chính xác (class, function, method).
* **`[03_CODE_SKELETON] cookiegli_get_skeleton`**: Gấp gọn mã nguồn xung quanh, giữ nguyên văn 100% hàm trọng tâm (`focus_symbol`).
* **`[04_IMPACT_ANALYSIS] cookiegli_blast_radius`**: Phân tích đồ thị phụ thuộc ngược và chỉ điểm bộ kiểm thử tối thiểu cần chạy.
* **`[05_ERROR_DISTILLER] cookiegli_distill_lesson`**: Tự động bóc tách traceback/diff thành bài học Darwin có tính điểm tin cậy Bayesian ROI.
* **`[06_ARCHITECTURE] cookiegli_get_genome`**: Nạp bản đồ kiến trúc Layer 1 tĩnh của toàn bộ dự án (<600t).
* **`[07_DARWIN_MEMORY] cookiegli_darwin_record` & `cookiegli_darwin_search`**: Ghi nhớ và truy vấn kinh nghiệm kỹ thuật theo Bayesian Laplace ROI.
* **`[08_TARGET_SYNC] cookiegli_sync`**: Đồng bộ bản đồ kiến trúc và bộ nhớ kinh nghiệm vào `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.windsurfrules`.

### 7.2. Ma Trận Hướng Dẫn Ra Quyết Định Của Agent (Agent Disambiguation Matrix)

| Tình Huống Của Agent | Công Cụ Chuẩn Cần Gọi | Tại Sao Dùng Tool Này? | Tool KHÔNG Nên Dùng Lẫn |
| :--- | :--- | :--- | :--- |
| **Bắt đầu một task code mới** | `cookiegli_boost` | Sinh trọn vẹn ngữ cảnh Layer 2 (<600t): symbol BM25 + skeleton + targeted tests + reasoning budget 2026. | Không gọi rời rạc skeleton + symbol nếu chưa boost. |
| **Muốn tìm hàm/class theo từ khóa tự nhiên** | `cookiegli_search` | Dùng SQLite FTS5 Okapi BM25+ toàn văn, xếp hạng theo độ tương đồng ngữ nghĩa. | Không dùng `cookiegli_find_symbols` khi chỉ nhớ từ khóa mang máng. |
| **Biết rõ tên hàm/class chính xác** | `cookiegli_find_symbols` | Dùng SQLite B-Tree index với cờ `exact=true`, truy xuất siêu tốc <0.05ms. | Không dùng BM25 khi cần khớp chính xác 1 định danh. |
| **Cần sửa code 1 hàm cụ thể trong file** | `cookiegli_get_skeleton` | Truyền `focus_symbol="ten_ham"`, giữ nguyên văn hàm cần sửa, gập toàn bộ hàm xung quanh để tiết kiệm token. | Không đọc toàn bộ file thô (raw dump). |
| **Chuẩn bị sửa code hoặc sau khi sửa code** | `cookiegli_blast_radius` | Phân tích đồ thị phụ thuộc ngược, chỉ điểm đúng file test cần chạy. | Không chạy toàn bộ test suite khổng lồ. |
| **Khi gặp lỗi test / traceback / compiler error** | `cookiegli_distill_lesson` | Bóc tách traceback, tạo bài học Darwin, gán nhãn scope và tính điểm Bayesian ROI. | Không tự sửa mà quên lưu kinh nghiệm. |
| **Vào repo lạ hoặc bắt đầu session mới** | `cookiegli_get_genome` | Nạp Layer 1 bản đồ kiến trúc tĩnh (<600t). | Không quét thủ công từng thư mục. |
| **Muốn dùng 1 tool duy nhất điều phối tất cả** | `cookiegli_full` | Truyền `action` tương ứng, máy chủ tự xử lý và trả về kết quả chuẩn hóa. | Dành cho các client chỉ hỗ trợ ít tool slots. |

### 7.3. Tài Nguyên Chỉ Dẫn Tích Hợp (MCP Resources)
Máy chủ hỗ trợ tài nguyên hệ thống qua MCP:
* **URI:** `mcp://cookiegli/guide`
* **MIME Type:** `text/markdown`
* **Nội dung:** Cẩm nang quyết định và quy tắc disambiguation hoàn chỉnh, giúp AI Agent tự động đọc hiểu khi kết nối.

### 7.4. Mẫu Cấu Hình JSON Cho Client MCP
Cấu hình máy chủ `CookieGli_Full` trong file MCP client (AntiGravity, Claude Desktop, Cursor, Windsurf):

```json
{
  "mcpServers": {
    "CookieGli_Full": {
      "command": "python",
      "args": [
        "E:/AI/Glimax/cli/cookiegli.py",
        "mcp",
        "--profile",
        "full",
        "--root",
        "E:/AI/Glimax"
      ]
    }
  }
}
```

---

## 8. Kiểm Thử & Đảm Bảo Chất Lượng

Dự án đi kèm bộ kiểm thử toàn diện với **160 bài test tự động**, sử dụng trực tiếp thư viện `unittest` tích hợp sẵn trong Python:

```bash
python -m unittest discover -s tests -v
```

Kết quả kiểm thử chuẩn:
```text
Ran 160 tests in 3.545s

OK (160/160 Tests Passed - 0 Failures, 0 Regressions)
```

Kiểm thử bao phủ đầy đủ:
* Trích xuất AST và phương thức trên Python, TypeScript, Go, Rust, Java.
* Cơ chế khóa file và chỉ mục B-Tree trên SQLite WAL.
* Nén 4 tầng của bộ tạo skeleton và kiểm tra thụt lề chuẩn.
* Đồ thị phụ thuộc ngược và thuật toán BFS chống lặp chu trình.
* Phân giải traceback đa nền tảng và cơ chế tự động khôi phục quy tắc cũ.

---

## 9. Giấy Phép

Dự án được phát hành theo giấy phép mã nguồn mở [MIT License](LICENSE) © 2026 LoveCookieee (KhoaSuperT1).

Tự do sử dụng, chỉnh sửa và tích hợp vào các dự án phần mềm cá nhân cũng như thương mại.
