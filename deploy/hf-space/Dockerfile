# HF Space — Streamlit qua Docker.
#
# VÌ SAO CÓ FILE NÀY: HuggingFace **đã bỏ SDK `streamlit`** cho Space tạo mới —
# API chỉ còn nhận `gradio|docker|static` (kiểm 2026-09-14). Streamlit nay là một
# **template Docker** (`streamlit/streamlit-template-space`). Nên app Streamlit
# muốn lên Space thì phải tự mang Dockerfile.
#
# Hệ quả kéo theo: `streamlit` PHẢI nằm trong `requirements.txt` — trước đây SDK
# tự cài hộ, giờ không ai cài hộ nữa.

FROM python:3.11-slim

# Vì sao 3.11 chứ không 3.13 (bản Đạt chạy local): 3.11 có wheel dựng sẵn cho
# gần như mọi gói trong chuỗi torch/transformers/FlagEmbedding. Thiếu wheel là
# rơi vào biên dịch từ nguồn ngay trên máy build của Space — chậm và hay gãy.

# HF Spaces chạy container dưới uid 1000. Tạo đúng user đó rồi làm mọi thứ
# trong HOME của nó: cache model của HuggingFace và file cấu hình của Streamlit
# đều cần chỗ GHI ĐƯỢC, chạy bằng root rồi đổi user sau là hỏng quyền.
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# Cài dependency TRƯỚC khi copy code: lớp này nặng (torch CPU + transformers +
# FlagEmbedding) nhưng đổi hiếm, nên Docker cache lại được. Sửa code rồi build
# lại thì không phải tải lại vài trăm MB.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Layout phải giữ nguyên hình dạng repo: `src/config.py` suy ra gốc repo bằng
# `Path(__file__).parent.parent`, rồi tìm `config/` cạnh `src/`. Đổi chỗ 3 thư
# mục này là `load_config()` không thấy `config.yaml`.
COPY --chown=user app    ./app
COPY --chown=user src    ./src
COPY --chown=user config ./config

# 7860 là cổng mặc định của Docker Space; phải khớp `app_port` trong README.
EXPOSE 7860

# `--server.address=0.0.0.0` bắt buộc: mặc định Streamlit chỉ nghe localhost,
# và trong container thì không ai ngoài container gọi tới được.
# `--server.headless=true` để nó đừng cố mở trình duyệt và đừng hỏi email.
CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
