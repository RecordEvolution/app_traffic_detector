FROM ultralytics/ultralytics:8.1.29-jetson

RUN apt-get -y update && apt-get -y upgrade && \
	apt-get install -y \
		libmicrohttpd-dev libjansson-dev \
		libssl-dev libsofia-sip-ua-dev libglib2.0-dev \
		libopus-dev libogg-dev libcurl4-openssl-dev liblua5.3-dev \
		libconfig-dev pkg-config libtool automake \
		libavutil-dev \
		libavformat-dev \
		libavcodec-dev \
		## libusrsctp1 \
		libwebsockets-dev \
		# libnanomsg5 \
		meson \
		# libnice-dev \
		##  libsrtp2-dev \
		# libnss3-dev \
		# extras
		libgtk-3-dev \
		curl \
		ffmpeg \
		unzip nginx procps v4l-utils git \
		usbutils udev && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y 

RUN cd /tmp && \
	wget https://github.com/cisco/libsrtp/archive/v2.5.0.tar.gz && \
	tar xfv v2.5.0.tar.gz && \
	cd libsrtp-2.5.0 && \
	./configure --prefix=/usr --enable-openssl && \
	make shared_library && \
	make install

WORKDIR /usr/local/src

RUN cd /tmp && \
	git clone https://gitlab.freedesktop.org/libnice/libnice && \
	cd libnice && \
	git checkout 0.1.21 && \
	meson builddir && \
  	ninja -C builddir && \
	ninja -C builddir install

RUN git clone --depth=1 https://github.com/meetecho/janus-gateway.git && \
    cd /usr/local/src/janus-gateway && \
	sh autogen.sh && \
	./configure --enable-post-processing --disable-rabbitmq --disable-mqtt --disable-plugin-videoroom --disable-aes-gcm --enable-libsrtp2 --prefix=/usr/local && \
	make && \
	make install && \
	make configs

WORKDIR /app

RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash \
	&& . /root/.bashrc && nvm install 18.0.0

# RUN wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt -O yolov8.pt
RUN wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s-obb.pt -O yolov8s-obb.pt 
RUN wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.pt -O yolov8s.pt 
# RUN wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8m.pt -O yolov8.pt 
# RUN wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8l.pt -O yolov8.pt 
RUN wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8x.pt -O yolov8x.pt
RUN wget https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov9c.pt -O yolov9c.pt

COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install -r requirements.txt


# For live developing code in your running container install the vscode cli and start a tunnel with `./code tunnel` in the /app folder
# RUN curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-arm64' --output vscode_cli.tar.gz &&\
# 	tar -xf vscode_cli.tar.gz

COPY web /app/web
RUN cd web && . /root/.bashrc && bun i && bun run build

COPY backend/package.json /app/backend/
RUN cd /app/backend && bun i

COPY backend/* /app/backend/

RUN rm -rf /usr/src/ultralytics/ultralytics/assets/*

COPY janus/* /usr/local/etc/janus/
COPY entrypoint.sh .reswarm/env-template.yml .reswarm/port-template.yml /app/

COPY video /app/video

CMD ["./entrypoint.sh"]