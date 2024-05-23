# Use the NVIDIA L4T TensorRT base image
FROM nvcr.io/nvidia/l4t-jetpack:r35.3.1

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    wget \
    curl \
	libssl-dev \
	gstreamer1.0-tools gstreamer1.0-plugins-bad gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly gstreamer1.0-libav \
	ffmpeg \
	openssh-server \
	unzip nginx procps v4l-utils git \
	usbutils udev && \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to the latest version
RUN pip3 install --upgrade pip

# --------------------------- My Stuff -----------------------

WORKDIR /app/video

COPY requirements.txt requirements.txt
RUN python3 -m pip install -r requirements.txt

# needs to be done seperately cus you can't install with no deps in requirements.txt
RUN python3 -m pip install supervision --no-deps


RUN mkdir -p /app/download

RUN rm -rf /usr/src/ultralytics/ultralytics/assets/*

COPY patch/polygon_zone.py /usr/local/lib/python3.8/dist-packages/supervision/detection/tools/polygon_zone.py

COPY . /app/video

RUN echo "PubkeyAuthentication yes" >> /etc/ssh/sshd_config

ENTRYPOINT ["/app/video/entrypoint.sh"]