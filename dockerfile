# Stage 1: Build the Swift app with Swift 6.0
FROM swift:6.0-jammy AS builder

# Copy only the swift directory into the container at /swift
COPY ./server /server

# Set the working directory to /swift/web
WORKDIR /server/web

# Build your Swift app from /swift/web
RUN swift build -c release
# Greatly reduces the size of the binary by stripping debug symbols
RUN strip --strip-unneeded /server/web/.build/release/boss

# Stage 2: Runtime image with Debian Slim (glibc-based)
# NOTE: Unfortunately `bullseye-slim` doesn't work because it has older
# versions of glibc, which 6.0-jammy builds with.
FROM debian:bookworm-slim

COPY . /boss
COPY private/dev-config /root/.boss/config

WORKDIR /boss

# FIXME: Not sure about this one... this allows for uploads, but should only be
# allowed by user running server.
RUN chmod -R o+rx /boss/public
RUN mkdir -p /root/db
RUN mkdir -p /root/logs
RUN mkdir -p /root/sandbox

# Install dependencies incl. Python3 and Swift runtime essentials
RUN apt-get update --allow-insecure-repositories
RUN apt-get install -y --no-install-recommends python3-minimal libatomic1 libcurl4 nginx git-lfs sqlite3 python3-pip python3-venv zsh procps
RUN apt-get clean && rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/*

# Note: This installs Python packages system-wide. A container is a
# single purpose virtual environment. It's redundant to create another.
RUN cd private && pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# TODO: Copy prod `nginx.com`. Ensure certs are created successfully.
COPY private/dev-nginx.conf /etc/nginx/sites-available/default

# TODO: Get this working for production image
#RUN sudo snap install --classic certbot
#RUN ln -s /snap/bin/certbot /usr/bin/certbot

# Copy Swift runtime libraries from the builder

# Copies over all swift binaries
#COPY --from=builder /usr/lib/swift/linux /usr/lib/swift/linux

# Copy specific files required by boss
COPY --from=builder /usr/lib/swift/linux/libswiftCore.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswift_Concurrency.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswift_StringProcessing.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswift_RegexParser.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswiftGlibc.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libBlocksRuntime.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libdispatch.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswiftDispatch.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libFoundation.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libFoundationEssentials.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libFoundationInternationalization.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/lib_FoundationICU.so /usr/lib/swift/linux/
COPY --from=builder /usr/lib/swift/linux/libswiftSynchronization.so /usr/lib/swift/linux/

# Copy the compiled Swift binary from the correct build path
COPY --from=builder /server/web/.build/release/boss /usr/local/bin/boss

# Set the working directory
WORKDIR /boss

# Ensure the binary can find the Swift libs
ENV LD_LIBRARY_PATH=/usr/lib/swift/linux:$LD_LIBRARY_PATH

CMD ["./bin/entry"]
