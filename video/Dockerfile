FROM ultralytics/ultralytics:8.2.19-jetson

RUN apt-get -y update && \
	apt-get install -y \
		libssl-dev \
		libavutil-dev \
		libavformat-dev \
		libavcodec-dev \
		gstreamer1.0-tools gstreamer1.0-plugins-bad gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly gstreamer1.0-libav \
		curl \
		ffmpeg \
		openssh-server \
		unzip nginx procps v4l-utils git \
		usbutils udev && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/*

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