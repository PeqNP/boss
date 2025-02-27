# Stage 1: Build the Swift app with Swift 6.0
FROM swift:6.0-jammy AS builder

# Copy only the swift directory into the container at /swift
COPY ./swift /swift

# Set the working directory to /swift/web
WORKDIR /swift/web

# Build your Swift app from /swift/web
RUN swift build -c release

# Stage 2: Runtime image with Debian Slim (glibc-based)
FROM debian:bullseye-slim

# Install basic dependencies, Python3, and Swift runtime essentials
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libatomic1 \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

# Copy Swift runtime libraries from the builder (Ubuntu-based, glibc)
COPY --from=builder /usr/lib/swift/linux /usr/lib/swift/linux

# Copy the compiled Swift binary from the correct build path
COPY --from=builder /swift/web/.build/release/boss /usr/local/bin/boss

# Set the working directory
WORKDIR /app

# Ensure the binary can find the Swift libs
ENV LD_LIBRARY_PATH=/usr/lib/swift/linux:$LD_LIBRARY_PATH

# Command to run your app (temporary, for testing)
#CMD ["/usr/local/bin/boss"]
