FROM python:3.13-slim
WORKDIR /app
COPY demo/service.py /app/service.py
USER 65532:65532
EXPOSE 8080
CMD ["python", "service.py"]
