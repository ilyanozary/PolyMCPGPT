# Dockerfile — حرفه‌ای، چندمنظوره، بهینه
FROM python:3.11-slim

# جلوگیری از بافر و لاگ‌گیری بهتر
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# نصب supervisor برای ران کردن چند پروسه
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# کپی و نصب وابستگی‌ها اول (بهترین کش داکر)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی همه فایل‌های پروژه
COPY . .

# کپی کانفیگ supervisor
COPY supervisord.conf /etc/supervisord.conf

# پورت‌های مورد نیاز
EXPOSE 8501   
# Streamlit
# MCP از stdio استفاده می‌کنه → پورت لازم نداره

# ران کردن supervisor (همه چیز با هم بالا میاد)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]