FROM python:3.12-slim

# Install industrial data science and reporting libraries
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    openpyxl \
    python-docx \
    reportlab \
    Pillow

# Create non-root unprivileged execution user
RUN groupadd -g 10001 sandbox && \
    useradd -u 10001 -g sandbox -m -s /bin/false sandbox

USER 10001:10001
WORKDIR /workspace
CMD ["python3"]
