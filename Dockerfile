FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create a system-level user and group named 'appuser'.
# The --system flag creates a user without a password or a home directory,
# which is a security best practice for running services as it's a non-interactive account.
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
RUN chown -R appuser:appuser /app

USER appuser

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:5000", "server.app:app"]