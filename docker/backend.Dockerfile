FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app/
COPY docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
RUN chmod 0755 /usr/local/bin/backend-entrypoint

EXPOSE 8000

ENTRYPOINT ["backend-entrypoint"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
