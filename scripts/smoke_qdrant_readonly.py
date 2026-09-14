"""Nghiệm thu key Qdrant CHỈ-ĐỌC trước khi dán vào HF Space Secrets.

Chạy:
    python scripts/smoke_qdrant_readonly.py              # hỏi key bằng ô nhập ẩn
    python scripts/smoke_qdrant_readonly.py --from-env   # dùng key .env/biến môi trường

**Vì sao cần script riêng thay vì `smoke_qdrant.py`:** file kia chỉ trả lời
*"kết nối được không"*. Câu hỏi của Tuần 7 khác hẳn — *"key này có BỊ CHẶN GHI
không"*. Một key toàn quyền pass `smoke_qdrant.py` sạch sẽ, rồi nằm trong Secrets
của một Space công khai với nguyên quyền `delete_collection`. Mất 2 collection =
index lại một session GPU Kaggle (~6,2h).

**Nghiệm thu = ĐỌC pass VÀ GHI fail.** Chỉ một trong hai thì key chưa dùng được:
đọc fail -> Space không chạy; ghi pass -> Space cầm dao.

**Vì sao mặc định hỏi bằng ô nhập ẩn, không đọc `.env`:** key đang nghiệm thu là
key MỚI, chưa nên nằm trong `.env` (chỗ đó là của key toàn quyền dùng cho
`build_index.py` — đổi nhầm là lần index lại sau chết lặng). Trên PowerShell cũng
không có tiền tố `VAR=x lệnh` như bash, nên ô nhập ẩn là đường duy nhất không để
key rơi vào lịch sử shell.

Script **không bao giờ in key** — chỉ in dấu vân tay che (6 ký tự đầu + độ dài).
Không ghi gì lên cluster ngoài một collection rác ở bước [3], và chỉ khi key hoá
ra vẫn ghi được; collection đó bị dọn ngay trong `finally`.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # cp1252 cắn tiếng Việt trên Windows

from src.config import load_config  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #
def _van_tay(key: str) -> str:
    """Dấu vân tay che của key — đủ để phân biệt hai key, không đủ để dùng."""
    return f"{key[:6]}...(len={len(key)})" if key else "(rỗng)"


def _la_tu_choi_quyen(exc: BaseException) -> bool:
    """Ngoại lệ này có phải *bị từ chối vì thiếu quyền* không?

    401/403 = từ chối, đúng thứ ta muốn thấy ở nhánh ghi.

    ⚠️ **404 KHÔNG phải từ chối** — nó nghĩa là lệnh ghi ĐƯỢC PHÉP chạy và chỉ
    không tìm thấy đối tượng. Đọc nhầm 404 thành "an toàn" là đúng cách một key
    toàn quyền lọt qua vòng nghiệm thu này.
    """
    code = getattr(exc, "status_code", None)
    if code in (401, 403):
        return True
    if code is not None:
        return False
    text = str(exc).lower()
    return any(
        t in text for t in ("forbidden", "unauthorized", "permission", "access denied")
    )


def _ma_loi(exc: BaseException) -> str:
    code = getattr(exc, "status_code", None)
    return type(exc).__name__ + (f" [{code}]" if code is not None else "")


# --------------------------------------------------------------------------- #
# 4 phép thăm dò
# --------------------------------------------------------------------------- #
def probe_doc_collection(client) -> tuple[bool, list[str]]:
    """[1] ĐỌC danh sách collection. Phải PASS."""
    try:
        ten = [c.name for c in client.get_collections().collections]
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL - không liệt kê được collection: {_ma_loi(exc)}: {exc}")
        return False, []
    print(f"  PASS - thấy {len(ten)} collection: {ten or '(rỗng)'}")
    return True, ten


def probe_doc_diem(client, mong_doi: list[str], co_san: list[str]) -> bool:
    """[2] ĐỌC ĐIỂM trong từng collection Space sẽ dùng. Phải PASS.

    Tách khỏi probe [1] có chủ đích: một key giới hạn theo collection vẫn liệt kê
    được tên nhưng **đọc điểm thì bị chặn**. Space cần đọc điểm, không cần đọc tên
    — nên [1] xanh mà [2] đỏ là đúng cái bẫy script này sinh ra để bắt.
    """
    ok = True
    for ten in mong_doi:
        if ten not in co_san:
            print(f"  FAIL - `{ten}` KHÔNG có trên cluster "
                  f"(key sai cluster, hoặc collection đã bị xoá)")
            ok = False
            continue
        try:
            n = client.count(collection_name=ten, exact=False).count
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL - `{ten}` liệt kê được nhưng KHÔNG đọc được điểm: "
                  f"{_ma_loi(exc)} (key bị giới hạn ra ngoài collection này)")
            ok = False
            continue
        print(f"  PASS - `{ten}` đọc được, ~{n:,} point")
    return ok


def probe_ghi_bi_chan(client, co_san: list[str]) -> tuple[bool, str | None]:
    """[3] GHI phải BỊ TỪ CHỐI. Trả về ``(đạt, tên_rác_cần_dọn)``.

    Thăm dò bằng ``create_collection`` trên một cái tên rác, **không** bằng
    ``delete_collection`` trên collection thật: nếu key hoá ra vẫn toàn quyền thì
    phép thử phải vô hại, chứ không được tự gây ra đúng tai nạn nó đi tìm.
    """
    ten_rac = f"_probe_readonly_{uuid.uuid4().hex[:8]}"
    if ten_rac in co_san:  # thắt lưng an toàn: xác suất ~0 nhưng rẻ
        print("  BỎ QUA - tên rác trùng collection có thật, chạy lại script.")
        return False, None

    from qdrant_client import models

    try:
        client.create_collection(
            collection_name=ten_rac,
            vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE),
        )
    except Exception as exc:  # noqa: BLE001
        if _la_tu_choi_quyen(exc):
            print(f"  PASS - tạo collection BỊ TỪ CHỐI ({_ma_loi(exc)}). Đúng ý muốn.")
            return True, None
        print(f"  KHÔNG KẾT LUẬN ĐƯỢC - lỗi không phải thiếu quyền: "
              f"{_ma_loi(exc)}: {exc}")
        return False, None

    print(f"  FAIL - TẠO ĐƯỢC `{ten_rac}`. Key này VẪN GHI ĐƯỢC, không phải read-only.")
    return False, ten_rac


def probe_xoa_bi_chan(client, co_san: list[str]) -> bool | None:
    """[4] XOÁ phải BỊ TỪ CHỐI. ``True``/``False``, hoặc ``None`` = không kết luận.

    Thăm dò trên một cái tên **chắc chắn không tồn tại** nên rủi ro bằng 0 kể cả
    khi key toàn quyền. Quyền được kiểm trước sự tồn tại, nên key chỉ-đọc ăn 403
    bất kể tên có thật hay không.

    Lệnh chạy lọt **không ngoại lệ nào** = key mang được động từ xoá = hỏng.
    404 thì mập mờ (tuỳ phiên bản server) -> cảnh báo, không chặn: [3] là cửa chính.
    """
    ten = f"_probe_khong_ton_tai_{uuid.uuid4().hex[:8]}"
    if ten in co_san:
        return None
    try:
        client.delete_collection(collection_name=ten)
    except Exception as exc:  # noqa: BLE001
        if _la_tu_choi_quyen(exc):
            print(f"  PASS - lệnh xoá BỊ TỪ CHỐI ({_ma_loi(exc)}).")
            return True
        print(f"  KHÔNG KẾT LUẬN ĐƯỢC - {_ma_loi(exc)} (không phải 401/403). "
              f"Tin kết quả [3].")
        return None
    print("  FAIL - lệnh xoá CHẠY LỌT không lỗi. Key mang được động từ xoá.")
    return False


def don_rac(client, ten_rac: str) -> None:
    """Dọn collection rác do [3] tạo ra. Tạo được thì gần như chắc xoá được."""
    try:
        client.delete_collection(collection_name=ten_rac)
    except Exception as exc:  # noqa: BLE001
        print(f"\n  DỌN RÁC THẤT BẠI - `{ten_rac}` CÒN TRÊN CLUSTER: {_ma_loi(exc)}")
        print(f"  Xoá tay trong console Qdrant. Tên: {ten_rac}")
        return
    print(f"  Đã dọn collection rác `{ten_rac}`.")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Nghiệm thu key Qdrant chỉ-đọc trước khi dán vào HF Space Secrets."
    )
    ap.add_argument("--from-env", action="store_true",
                    help="Dùng QDRANT_API_KEY từ .env/biến môi trường thay vì hỏi. "
                         "Mặc định là hỏi, để key mới không phải ghi vào .env.")
    ap.add_argument("--size", type=int, action="append", metavar="N",
                    help="Chunk size cần kiểm (lặp lại được). Mặc định: index.sizes.")
    args = ap.parse_args()

    cfg = load_config()
    url = cfg.qdrant.url

    if not url:
        print("FAIL: QDRANT_URL rỗng. Điền REST endpoint của cluster vào .env -")
        print("      https://<cluster-id>.<region>.cloud.qdrant.io:6333")
        return 2
    if url.startswith("https://cloud.qdrant.io/"):
        print("FAIL: QDRANT_URL đang là URL trang dashboard, không phải REST endpoint.")
        print("      Lấy đúng endpoint ở mục 'Endpoint' trên trang cluster overview.")
        return 2

    if args.from_env:
        # .strip() BẮT BUỘC: đường `$env:X = Get-Clipboard` rất hay kéo theo
        # xuống dòng/khoảng trắng thừa, và key thừa 1 ký tự thì server trả 401 —
        # triệu chứng giống hệt "key sai quyền", tốn cả buổi đi nhầm hướng.
        key, nguon = (cfg.qdrant.api_key or "").strip(), ".env / biến môi trường"
        if not key:
            print("FAIL: --from-env nhưng QDRANT_API_KEY rỗng.")
            return 2
    elif not sys.stdin.isatty():
        # getpass cần console thật. Terminal tích hợp của IDE thường không phải,
        # và lúc đó nó fail im lặng hoặc không nhận paste — đừng để người dùng
        # đoán, chỉ thẳng đường đi được.
        print("FAIL: stdin không phải console thật nên ô nhập ẩn không dùng được.")
        print("      Dùng đường biến môi trường (key KHÔNG vào .env, KHÔNG vào")
        print("      lịch sử shell — copy key rồi chạy trong PowerShell):")
        print()
        print('        $env:QDRANT_API_KEY = (Get-Clipboard -Raw).Trim()')
        print("        python scripts/smoke_qdrant_readonly.py --from-env")
        print('        Remove-Item Env:\\QDRANT_API_KEY')
        return 2
    else:
        from getpass import getpass
        print("Dán key CẦN NGHIỆM THU (ô nhập ẩn: không vào lịch sử shell, "
              "không ghi ra đâu cả).")
        print("Terminal không cho paste? Ctrl+C rồi xem `--from-env` trong --help.")
        key, nguon = getpass("  QDRANT_API_KEY: ").strip(), "ô nhập ẩn"
        if not key:
            print("FAIL: không nhập key.")
            return 2

    sizes = args.size or list(cfg.index.sizes)
    mong_doi = [collection_name(cfg.qdrant.collection, s) for s in sizes]

    print(f"\nCluster : {url}")
    print(f"Key     : {_van_tay(key)}  (nguồn: {nguon})")
    print(f"Cần đọc : {mong_doi}\n")

    from qdrant_client import QdrantClient

    client = QdrantClient(url=url, api_key=key, timeout=30)
    ten_rac: str | None = None

    try:
        print("[1] ĐỌC danh sách collection - phải PASS")
        p1, co_san = probe_doc_collection(client)

        print("\n[2] ĐỌC ĐIỂM trong collection Space dùng - phải PASS")
        if p1:
            p2 = probe_doc_diem(client, mong_doi, co_san)
        else:
            print("  BỎ QUA - [1] hỏng nên không có danh sách để đối chiếu.")
            p2 = False

        print("\n[3] TẠO collection - phải BỊ TỪ CHỐI")
        p3, ten_rac = probe_ghi_bi_chan(client, co_san)

        print("\n[4] XOÁ collection - phải BỊ TỪ CHỐI")
        p4 = probe_xoa_bi_chan(client, co_san)
    finally:
        if ten_rac:
            don_rac(client, ten_rac)

    doc_ok = p1 and p2
    ghi_bi_chan = p3 and (p4 is not False)

    print("\n" + "=" * 68)
    print(f"  ĐỌC được   : {'CÓ' if doc_ok else 'KHÔNG'}")
    print(f"  GHI bị chặn : {'CÓ' if ghi_bi_chan else 'KHÔNG'}")
    print("=" * 68)

    if doc_ok and ghi_bi_chan:
        print("ĐẠT - key này dán vào HF Space Secrets được.")
        print("  Tên biến trên Space: QDRANT_URL + QDRANT_API_KEY")
        print("  (khớp config.yaml:132-133; config.py dùng os.environ.setdefault nên")
        print("   Secrets của Space thắng .env -> KHÔNG cần sửa code.)")
        return 0

    print("CHƯA ĐẠT - ĐỪNG dán key này vào Space.")
    if not doc_ok:
        print("  - Đọc hỏng: key sai cluster, hoặc scope không phủ collection cần dùng.")
    if not ghi_bi_chan:
        print("  - Ghi không bị chặn: đây là key TOÀN QUYỀN. Tạo lại key với")
        print("    Access = Read-only, scope = đúng các collection ở trên.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
