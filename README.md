# 🍪 CookieGli

<p align="center">
  <strong>Enterprise-Grade Context Genome Compressor & Bayesian Darwinian Memory for Autonomous AI Agents</strong><br>
  <em>Zero 3rd-Party Dependencies • Pure Python stdlib • 100% Cross-Platform (Windows / Linux / macOS)</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%E2%89%A53.9-blue.svg?style=flat-square" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/tests-100%25%20passing-brightgreen.svg?style=flat-square" alt="Tests Passing">
  <img src="https://img.shields.io/badge/dependencies-zero%20(stdlib%20only)-orange.svg?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-informational.svg?style=flat-square" alt="Cross Platform">
  <img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="MIT License">
</p>

---

## 📑 Mục Lục (Table of Contents)
- [1. Tại Sao Lại Là CookieGli? (Why CookieGli?)](#1-tại-sao-lại-là-cookiegli-why-cookiegli)
- [2. Kiến Trúc Cốt Lõi (Core Architecture)](#2-kiến-trúc-cốt-lõi-core-architecture)
- [3. So Sánh Tính Năng (Feature Matrix vs Naive vs Legacy)](#3-so-sánh-tính-năng-feature-matrix-vs-naive-vs-legacy)
- [4. Cài Đặt & Khởi Động Nhanh (Quick Start)](#4-cài-đặt--khởi-động-nhanh-quick-start)
- [5. Hướng Dẫn Lệnh CLI (CLI Command Reference)](#5-hướng-dẫn-lệnh-cli-cli-command-reference)
- [6. Mô Hình Toán Học Tiến Hóa ROI (Bayesian ROI Dynamics)](#6-mô-hình-toán-học-tiến-hóa-roi-bayesian-roi-dynamics)
- [7. Quy Trình Vận Hành Cho AI Agent (.agents Standard)](#7-quy-trình-vận-hành-cho-ai-agent-agents-standard)
- [8. Kiểm Thử & Nghiệm Thu (Test Suite & Verification)](#8-kiểm-thử--nghiệm-thu-test-suite--verification)
- [9. Giấy Phép (License)](#9-giấy-phép-license)

---

## 1. Tại Sao Lại Là CookieGli? (Why CookieGli?)

Mọi phiên làm việc kéo dài của AI Agent (Antigravity, Claude Code, Cursor, Windsurf, v.v.) đều đối mặt với kẻ thù chung: **Context Window Bloat (Phình to ngữ cảnh)**.
- Khi nạp cả cây thư mục và mã nguồn thô, Agent tiêu tốn từ **30.000 đến 100.000 tokens** ngay từ lượt chat đầu tiên, gây suy giảm trí nhớ, tăng độ trễ và chi phí API khổng lồ.
- Các công cụ nén cũ thường chỉ dùng regex hời hợt hoặc gọi lệnh shell Unix (`date -u`, `2>/dev/null`, `grep | head`), gây **treo cứng tiến trình (freeze/hang) trên Windows** và làm hỏng file JSON state khi bị tắt đột ngột.

**CookieGli giải quyết triệt để vấn đề này:**
1. **High-Density AST Scanner:** Quét và trích xuất cấu trúc AST thực tế (Class hierarchy, Methods, Types, Async functions, Arrow functions, Dependencies) cho Python, JavaScript, TypeScript, Go, Rust, Java, C/C++.
2. **Genome Compression (< 600 tokens):** Nén toàn bộ codebase thành bản đồ kiến trúc cô đọng **≤ 600 tokens**, sẵn sàng nạp tức thì trong 0.1 giây.
3. **Bayesian Darwin Memory:** Lưu giữ và tiến hóa các bài học kinh nghiệm (Failure-to-Success learnings) bằng thuật toán Laplace smoothing, tự động đào thải mẫu thử thất bại và bảo vệ các pattern xuất sắc.
4. **Zero Runtime Overhead & 100% Pure Python:** Hoạt động an toàn tuyệt đối trên Windows, Linux và macOS, không phụ thuộc vào bất kỳ thư viện bên ngoài nào.

---

## 2. Kiến Trúc Cốt Lõi (Core Architecture)

```mermaid
graph TD
    A[Mã Nguồn Dự Án / Project Files] --> B[AstScanner: Deep Multi-Language AST]
    B -->|Minification & Size Filter| C[Structural File Entities]
    C --> D[GenomeEngine: 5 Architectural Blocks]
    
    subgraph GENOME_BLOCKS [5 Khối Kiến Trúc Tối Giản]
        D1[ArchitectureDNA: Ngôn ngữ, Frameworks, Entrypoints]
        D2[DependencyMatrix: Package ngoài & Hotspots fan-in]
        D3[ApiRegistry: Public Classes & Signatures]
        D4[PatternStandards: Quy ước đặt tên & Async paradigms]
        D5[EvolutionHotspots: Git Commits & Active TODOs]
    end
    
    D --> D1 & D2 & D3 & D4 & D5
    D1 & D2 & D3 & D4 & D5 --> E[GENOME.md: ~500 Tokens]
    
    E --> F[AI Agent Onboarding / Task Synthesis]
    F -->|Thực thi & Sửa lỗi| G[System Autopilot: Continuous Test Loop]
    G -->|Trích xuất bài học thành công| H[DarwinMemory: Bayesian Smoothed ROI]
    H -->|Atomic Persistence & Decay Pruning| I[Learned Knowledge Base]
```

---

## 3. So Sánh Tính Năng (Feature Matrix vs Naive vs Legacy)

| Tiêu Chí / Tính Năng | Quét Mã Nguồn Thô (Naive Dump) | Glimax Legacy (v1.0.0) | 🍪 CookieGli (v2.0.0) |
|---|---|---|---|
| **Lượng Token tiêu thụ** | 30.000 – 100.000 tokens | ~1.500 tokens (giả lập) | **300 – 600 tokens (Đo đạc thực tế)** |
| **Độ chính xác bóc tách AST** | 0% (phải đọc toàn bộ) | Thấp (Regex nông, bỏ sót TS/Arrow) | **Rất cao (Python AST + Multi-paradigm Regex)** |
| **Tương thích Windows** | Khá | ❌ **Treo tiến trình** (`date -u`, `2>/dev/null`) | ✅ **100% Native Safe (Pure Python stdlib)** |
| **Bảo vệ chống Minified Files** | ❌ Không | ❌ Không | ✅ **Tự động lọc file `.min.js` & long lines** |
| **Thuật toán chấm điểm ROI** | ❌ Không có | Dễ biến dạng do mẫu nhỏ (1 run = 76%) | ✅ **Bayesian / Laplace Smoothed ROI** |
| **An toàn lưu trữ (Persistence)** | N/A | Ghi đè file thô (dễ hỏng dữ liệu) | ✅ **Atomic File Swap (`os.replace`)** |
| **Tích hợp Agent** | N/A | Bắt Agent gọi CLI từng turn (tốn token) | ✅ **Tích hợp tự động qua `.agents/` & Skills** |

---

## 4. Cài Đặt & Khởi Động Nhanh (Quick Start)

### Yêu Cầu Hệ Thống:
* Python $\ge 3.9$ (đã kiểm thử trên Python 3.9, 3.10, 3.11, 3.12, 3.13, 3.14).
* **Zero 3rd-party dependencies** — Không cần `pip install` bất cứ gói nào!

### Cài Đặt:
```bash
git clone https://github.com/YourRepo/CookieGli.git
cd CookieGli
```

### 1. Sinh Bản Đồ Genome Cho Dự Án:
```bash
python cli/cookiegli.py genome build . --save .agents/GENOME.md
```

### 2. Tổng Hợp Ngữ Cảnh Cho Task Cụ Thể:
```bash
python cli/cookiegli.py genome context "Refactor authentication service and validate JWT"
```

### 3. Quản Lý Tri Thức Tiến Hóa Darwin:
```bash
# Đăng ký một bài học kinh nghiệm
python cli/cookiegli.py darwin register jwt_guard pattern "Always check expiration before token decode" --tags "auth,security"

# Ghi nhận kết quả sử dụng
python cli/cookiegli.py darwin use <artifact_id> true

# Tìm kiếm bài học theo tag
python cli/cookiegli.py darwin search --tags "auth"

# Chạy chu trình tiến hóa & cắt tỉa các pattern lỗi thời
python cli/cookiegli.py darwin evolve

# Đồng bộ trực tiếp vào AGENTS.md
python cli/cookiegli.py darwin sync
```

---

## 5. Hướng Dẫn Lệnh CLI (CLI Command Reference)

Tất cả thao tác được quản lý qua một file duy nhất `cli/cookiegli.py`:

```
cookiegli <engine> <action> [options]
```

### 🧬 Genome Engine (`cookiegli genome ...`)
| Lệnh | Tham Số | Mô Tả |
|---|---|---|
| `build` | `[path] [--max-tokens 1500] [--save PATH]` | Quét và sinh bản đồ nén Genome của codebase. |
| `context` | `<task> [path] [--max-tokens 1200]` | Trích xuất lát cắt ngữ cảnh theo từ khóa và Class/Method mục tiêu. |

### 🧠 Darwin Memory (`cookiegli darwin ...`)
| Lệnh | Tham Số | Mô Tả |
|---|---|---|
| `register` | `<name> <type> <content> [--tags TAGS]` | Đăng ký bài học mới (`pattern`, `lesson`, `skill`, `tool`). |
| `use` | `<artifact_id> <true\|false>` | Ghi nhận lượt sử dụng thành công hoặc thất bại. |
| `search` | `[--query TEXT] [--tags TAGS]` | Tìm kiếm nhanh bài học theo nội dung hoặc tag. |
| `list` | `[type]` | Liệt kê tất cả các bài học đang hoạt động sắp xếp theo điểm ROI. |
| `evolve` | `[--threshold 0.3] [--max-capacity 50] [--decay 0.95]` | Áp dụng generational decay và cắt tỉa (prune) các pattern kém hiệu quả. |
| `sync` | `[--agents-file PATH] [--max-tokens 500]` | Tự động đồng bộ bảng bài học vào file `.agents/AGENTS.md`. |

---

## 6. Mô Hình Toán Học Tiến Hóa ROI (Bayesian ROI Dynamics)

Để tránh hiện tượng điểm ROI bị thổi phồng hoặc suy giảm quá mức khi số lần sử dụng còn ít (Small-sample variance), CookieGli áp dụng công thức **Laplace Smoothing**:

$$\text{SR}_{\text{smooth}} = \frac{\text{Successes} + 1}{\text{Total Uses} + 2}$$

Điểm ROI tổng hợp được xác định bởi:

$$\text{ROI} = 0.7 \times \text{SR}_{\text{smooth}} + 0.3 \times \min\left(\frac{\text{Total Uses}}{5}, 1.0\right)$$

* **Khi mới khởi tạo (0 lần dùng):** $\text{SR} = \frac{0 + 1}{0 + 2} = 0.5 \implies \text{ROI} = 0.35$ (Mức khởi đầu công bằng).
* **Khi dùng 1 lần thành công (1 lần dùng):** $\text{SR} = \frac{1 + 1}{1 + 2} = 0.67 \implies \text{ROI} = 0.53$ (Không bị thổi lên 1.0).
* **Khi dùng 5 lần thành công liên tiếp:** $\text{SR} = \frac{5 + 1}{5 + 2} = 0.86 \implies \text{ROI} = 0.90$ (Chứng minh độ tin cậy tuyệt đối).
* **Quy luật Đào Thải (Decay & Pruning):** Sau mỗi thế hệ (`evolve`), $\text{ROI}_{g+1} = \text{ROI}_g \times 0.95$. Các pattern không được dùng hoặc thất bại liên tục sẽ rơi xuống dưới ngưỡng `0.30` và bị loại bỏ vĩnh viễn.

---

## 7. Quy Trình Vận Hành Cho AI Agent (.agents Standard)

Tệp [`.agents/AGENTS.md`](.agents/AGENTS.md) được thiết kế theo tiêu chuẩn công nghiệp:
1. **Onboarding First:** Luôn đọc `.agents/GENOME.md` đầu phiên làm việc để nắm 100% bản đồ dự án trong `< 600 tokens`.
2. **Deduplicate & Line-Range Reads:** Chỉ đọc đúng đoạn code cần sửa bằng `view_file(StartLine, EndLine)` hoặc `grep_search`.
3. **Continuous Engineering Loop:** Bắt buộc chạy Unit Test trước khi báo cáo hoàn thành. Nếu có bug, tự sửa đến khi Pass 100%.
4. **Learning Extraction:** Tự động ghi lại bài học thất bại $\rightarrow$ thành công vào bảng tri thức Darwin.

---

## 8. Kiểm Thử & Nghiệm Thu (Test Suite & Verification)

Toàn bộ hệ thống được bảo vệ bởi bộ Unit Test độc lập:

```powershell
python -m unittest discover -s tests -v
```

```
test_minified_file_guard (test_ast_scanner.TestAstScanner.test_minified_file_guard) ... ok
test_scan_python_file (test_ast_scanner.TestAstScanner.test_scan_python_file) ... ok
test_scan_typescript_and_arrow_functions (test_ast_scanner.TestAstScanner.test_scan_typescript_and_arrow_functions) ... ok
test_atomic_file_persistence (test_darwin_memory.TestDarwinMemory.test_atomic_file_persistence) ... ok
test_bayesian_smoothed_roi (test_darwin_memory.TestDarwinMemory.test_bayesian_smoothed_roi) ... ok
test_capacity_constraint_strict (test_darwin_memory.TestDarwinMemory.test_capacity_constraint_strict) ... ok
test_markdown_summary (test_darwin_memory.TestDarwinMemory.test_markdown_summary) ... ok
test_search_by_query_and_tags (test_darwin_memory.TestDarwinMemory.test_search_by_query_and_tags) ... ok
test_build_genome_compact (test_genome_engine.TestGenomeEngine.test_build_genome_compact) ... ok
test_synthesize_task_context_entity_targeting (test_genome_engine.TestGenomeEngine.test_synthesize_task_context_entity_targeting) ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.169s

OK (100% Pass)
```

---

## 9. Giấy Phép (License)

Dự án được phân phối dưới giấy phép mã nguồn mở [MIT License](LICENSE). Tự do sử dụng, chỉnh sửa và phân phối trong cả dự án cá nhân lẫn thương mại.
