FROM apache/airflow:3.2.2

# Install system dependencies
USER root
RUN apt-get update && apt-get install -y \
    cifs-utils \
    gcc \
    libpq-dev \
    python3-dev \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    default-jre \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# JAVA_HOME via symlink estándar de Debian — funciona en amd64 y arm64
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYTHONPATH="${PYTHONPATH}:/opt/airflow"

# Switch back to airflow user
USER airflow

# Copy your requirements.txt file into the container
COPY requirements.txt /tmp/requirements.txt

# Install the Airflow version specified and any additional requirements
RUN pip install apache-airflow==${AIRFLOW_VERSION} -r /tmp/requirements.txt

# Install Playwright browsers
RUN playwright install