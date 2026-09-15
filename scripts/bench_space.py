"""Đo latency trên HF Space THẬT — lái UI bằng Playwright, không giả lập.

    python scripts/bench_space.py                 # 2 lượt × 3 nhánh (ấm máy)
    python scripts/bench_space.py --repeat 3
    python scripts/bench_space.py --cold-start    # kèm pause/restart để đo cold

Ghi ra `data/processed/bench_space.json`, `build_perf_report.py` đọc vào mục 3.

## Vì sao cần script riêng thay vì đo local rồi suy ra

Space là **sản phẩm thật** — thứ hội đồng bấm vào. Local tách được stage nhưng
là chiếc laptop không ai dùng để chạy hệ. Hai cột trả lời hai câu khác nhau;
xem docstring `build_perf_report.py`.

## ⛔ MỘT BROWSER CHO CẢ LÔ — đây là phần quan trọng nhất của file này

2026-09-15 đo page-ready bằng cách bật **Chromium mới cho mỗi mẫu**:
8,1 · 5,9 · **103,7** s. Dùng **một** browser cho cả 5 mẫu: **5,7–8,3 s**, ổn
định. Đối chứng quyết định: `curl /_stcore/health` chạy **xen kẽ** vẫn
0,84–0,99 s suốt cả hai lần → nghẽn nằm ở **laptop đang đo**, không ở Space.
Phiên đó đã kết luận nhầm *"cold start 73–85 s"* rồi phải tự bác bỏ.

Nên script này mở **một** browser, và mỗi mẫu kèm `health_s` (một lượt HTTP
thuần, không qua trình duyệt) làm đối chứng. Health chậm theo = mạng/Space;
health nhanh mà page chậm = **máy đo bận**, số phải vứt.

⚠️ `playwright` là phụ thuộc **chỉ để đo**, cố ý KHÔNG nằm trong
`requirements.txt` của Space — Space không cần tự đo chính nó.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "bench_space.json"

SPACE_ID = "datvu107-dateddy/vimed"
URL = "https://datvu107-dateddy-vimed.hf.space"

#: Ba câu THẬT, mỗi câu ép pipeline đi một nhánh khác nhau.
CAU = [
    ("ABSTAIN — policy", "D-01",
     "Bác sĩ cho em uống metformin mà em làm mất toa rồi. "
     "Em 58 ký, sáng chiều mỗi lần bao nhiêu ạ?"),
    ("ANSWER", "E-01",
     "Biến chứng loét chân ở bệnh nhân tiểu đường có thể dẫn đến "
     "những biến chứng nguy hiểm nào?"),
    ("ABSTAIN — truy hồi", "A-02",
     "Đau ngực ở bệnh nhân hẹp van hai lá có thể do nguyên nhân nào?"),
]


def health_s() -> float:
    """Một lượt HTTP thuần, KHÔNG qua trình duyệt — đối chứng của phép đo."""
    r = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{time_total}", f"{URL}/_stcore/health"],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return -1.0


def mo_trang(browser):
    """Mở một tab mới tới Space, trả `(page, giây tới lúc dùng được)`."""
    pg = browser.new_page(viewport={"width": 1400, "height": 1000})
    t = time.perf_counter()
    pg.goto(URL, wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_selector("input[type='text']", timeout=180_000)
    return pg, time.perf_counter() - t


def hoi(pg, cauhoi: str, timeout_ms: int = 600_000) -> tuple[float, str, bool]:
    """Gõ câu hỏi, bấm, đợi badge action. Trả `(giây, action, có hiện nguồn)`."""
    o = pg.locator("input[type='text']").first
    o.fill("")
    o.fill(cauhoi)
    t0 = time.perf_counter()
    pg.get_by_role("button", name=re.compile("Hỏi")).first.click()
    pg.wait_for_function(
        "() => /action = (ANSWER|ANSWER_WITH_CAUTION|ABSTAIN)/.test(document.body.innerText)",
        timeout=timeout_ms,
    )
    dt = time.perf_counter() - t0
    txt = pg.inner_text("body")
    m = re.search(r"action = (\w+)", txt)
    return dt, (m.group(1) if m else "?"), bool(re.search(r"Nguồn \(\d+\)", txt))


def do_cold_start(p) -> dict:
    """Pause → restart → đo container lên RUNNING, rồi truy vấn đầu.

    Dùng câu **policy** làm phép đo: nó tốn **0 lượt LLM** và khi ấm chỉ mất
    ~0,6 s, nên gần như toàn bộ thời gian đo được LÀ nạp model.
    """
    print("[..] pause Space…")
    subprocess.run(["hf", "spaces", "pause", SPACE_ID], capture_output=True, text=True)
    time.sleep(5)
    t0 = time.perf_counter()
    subprocess.run(["hf", "spaces", "restart", SPACE_ID], capture_output=True, text=True)
    subprocess.run(["hf", "spaces", "wait", SPACE_ID], capture_output=True, text=True)
    container_s = time.perf_counter() - t0
    print(f"[ok] container lên RUNNING sau {container_s:.0f}s")

    b = p.chromium.launch(headless=True)
    pg, _ = mo_trang(b)
    dt, _, _ = hoi(pg, CAU[0][2])
    b.close()
    print(f"[ok] truy vấn đầu (policy, 0 lượt LLM) = {dt:.1f}s → gần như toàn bộ là nạp model")
    return {"container_s": round(container_s), "nap_model_s": round(dt)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--cold-start", action="store_true")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    ket: dict = {
        "space": SPACE_ID,
        "hardware": "cpu-basic",
        "ngay": date.today().isoformat(),
        "nhanh": {nhan: [] for nhan, _, _ in CAU},
        "page_ready": [],
        "health_s": [],
    }

    with sync_playwright() as p:
        if args.cold_start:
            ket["cold_start"] = do_cold_start(p)

        # ⛔ MỘT browser cho cả lô (xem docstring), nhưng TAB MỚI mỗi câu.
        #
        # ⚠️ Tái dùng cùng một tab là SAI, đã dính thật: `wait_for_function` dò
        # chuỗi `action = …` trong `innerText`, mà chuỗi của câu TRƯỚC vẫn còn
        # trên trang → nó trả về **ngay lập tức** với kết quả cũ. Triệu chứng:
        # `E-01` ra **0,0 s** và `action=ABSTAIN` (đúng ra ~20 s / ANSWER).
        # Số 0,0 s trông như "nhanh bất thường" chứ không như lỗi — đúng loại
        # sai âm thầm mà cả file này sinh ra để chống.
        #
        # Tab mới thì DOM sạch. Cái đắt là **browser**, không phải tab, nên
        # cách này giữ nguyên bài học "một browser cho cả lô".
        b = p.chromium.launch(headless=True)
        for lan in range(args.repeat):
            print(f"\n--- lượt {lan + 1}/{args.repeat} ---")
            for nhan, qid, q in CAU:
                h = health_s()
                pg, pr = mo_trang(b)
                ket["health_s"].append(round(h, 2))
                ket["page_ready"].append(round(pr, 1))
                dt, action, nguon = hoi(pg, q)
                pg.close()
                ket["nhanh"][nhan].append(round(dt, 1))
                print(
                    f"  {qid:<6} {nhan:<20} {dt:>6.1f}s  {action:<20} "
                    f"nguồn={'HIỆN' if nguon else 'ẨN'}  "
                    f"(page-ready {pr:.1f}s · health {h:.2f}s)"
                )
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ket, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ok] → {OUT.relative_to(ROOT)}")

    pr = ket["page_ready"]
    if pr and max(pr) > 3 * min(pr) and max(ket["health_s"]) < 2.0:
        print(
            f"⚠️  page-ready trải {min(pr):.1f}–{max(pr):.1f}s trong khi health giữ "
            f"< 2s → nghi MÁY ĐO bận, không phải Space. Chạy lại lúc máy rảnh."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
